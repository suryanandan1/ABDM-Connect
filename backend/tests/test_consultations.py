from datetime import timedelta

from conftest import login

from app.database import utcnow


def visit(**changes):
    body = {
        "patient_id": 2, "visit_at": (utcnow() - timedelta(hours=1)).isoformat(),
        "chief_complaint": "Headache for 3 days", "examination": "Alert, no neck stiffness",
        "diagnosis": "Tension-type headache", "advice": "Sleep well, limit screen time <b>please</b>",
        "follow_up_date": (utcnow() + timedelta(days=7)).date().isoformat(),
        "bp_systolic": 124, "bp_diastolic": 80, "pulse": 72, "temperature": 36.8, "spo2": 99, "weight": 70.5,
        "medications": [{"name": "Paracetamol 500 mg", "dosage": "1 tablet", "frequency": "Twice a day",
                         "duration": "3 days", "instructions": "After food"}],
    }
    return {**body, **changes}


def create(client, headers, **changes):
    r = client.post("/api/v1/consultations", json=visit(**changes), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_doctor_creates_and_patient_reads(client):
    doctor = login(client, "hospital1")
    c = create(client, doctor)
    assert c["status"] == "final" and c["doctor"]["full_name"] == "Dr. Kavita Rao"
    assert c["medications"][0]["frequency"] == "Twice a day"
    # The patient (ravi = patient 2) sees it in their list and can open it
    ravi = login(client, "ravi")
    assert [x["id"] for x in client.get("/api/v1/consultations", headers=ravi).json()] == [c["id"]]
    assert client.get(f"/api/v1/consultations/{c['id']}", headers=ravi).json()["diagnosis"] == "Tension-type headache"
    # The authoring hospital sees it in its list and on the patient page
    assert c["id"] in [x["id"] for x in client.get("/api/v1/consultations", headers=doctor).json()]
    assert [x["id"] for x in client.get("/api/v1/patients/2/consultations", headers=doctor).json()] == [c["id"]]


def test_only_author_facility_and_patient_have_access(client):
    c = create(client, login(client, "hospital1"))
    url = f"/api/v1/consultations/{c['id']}"
    for user in ("hospital2", "lab1", "admin", "asha"):
        assert client.get(url, headers=login(client, user)).status_code == 403, user
        assert client.get(url + "/fhir", headers=login(client, user)).status_code == 403, user
    # Another hospital does not see it in its lists either
    other = login(client, "hospital2")
    assert client.get("/api/v1/patients/2/consultations", headers=other).json() == []
    assert c["id"] not in [x["id"] for x in client.get("/api/v1/consultations", headers=other).json()]
    # Labs and patients cannot write consultations
    assert client.post("/api/v1/consultations", json=visit(), headers=login(client, "lab1")).status_code == 403
    assert client.post("/api/v1/consultations", json=visit(), headers=login(client, "ravi")).status_code == 403
    denied = client.get("/api/v1/audit-events?event_type=CONSULTATION_VIEW&outcome=DENIED", headers=login(client, "admin"))
    assert len(denied.json()) >= 4


def test_consultation_validation(client):
    doctor = login(client, "hospital1")

    def status(**changes):
        return client.post("/api/v1/consultations", json=visit(**changes), headers=doctor).status_code

    assert status(visit_at=(utcnow() + timedelta(days=1)).isoformat()) == 422
    assert status(chief_complaint="") == 422
    assert status(diagnosis=" ") == 422
    assert status(bp_systolic=80, bp_diastolic=90) == 422
    assert status(bp_systolic=120, bp_diastolic=None) == 422
    assert status(spo2=140) == 422
    assert status(follow_up_date=(utcnow() - timedelta(days=5)).date().isoformat()) == 422
    assert status(medications=[{"name": "X", "dosage": "", "frequency": "daily", "duration": "1 day"}]) == 422
    assert status(patient_id=999) == 404
    # Vitals, advice, follow-up and medicines are all optional
    minimal = {"patient_id": 2, "visit_at": (utcnow() - timedelta(minutes=5)).isoformat(),
               "chief_complaint": "Cough", "diagnosis": "Common cold"}
    assert client.post("/api/v1/consultations", json=minimal, headers=doctor).status_code == 201


def test_consultation_fhir_bundle_is_valid(client):
    c = create(client, login(client, "hospital1"))
    data = client.get(f"/api/v1/consultations/{c['id']}/fhir", headers=login(client, "ravi")).json()
    assert data["validation"]["valid"], data["validation"]["errors"]
    bundle = data["resource"]
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert types[0] == "Composition" and bundle["type"] == "document"
    assert {"Encounter", "Condition", "Observation", "MedicationRequest", "Appointment"} <= set(types)
    comp = bundle["entry"][0]["resource"]
    assert comp["type"]["coding"][0]["code"] == "11488-4"
    assert [s["title"] for s in comp["section"]] == [
        "Chief complaints", "Physical examination", "Diagnosis", "Medications", "Advice and follow-up"]
    # Free text is escaped inside the XHTML narrative
    assert "&lt;b&gt;please&lt;/b&gt;" in comp["section"][-1]["text"]["div"]
    bp = next(e["resource"] for e in bundle["entry"] if e["resource"]["id"].endswith("-bp"))
    assert [x["valueQuantity"]["value"] for x in bp["component"]] == [124, 80]

    # A minimal consultation still produces a valid bundle
    minimal = create(client, login(client, "hospital1"), examination=None, advice=None, follow_up_date=None,
                     bp_systolic=None, bp_diastolic=None, pulse=None, temperature=None, spo2=None, weight=None,
                     medications=[])
    data = client.get(f"/api/v1/consultations/{minimal['id']}/fhir", headers=login(client, "hospital1")).json()
    assert data["validation"]["valid"], data["validation"]["errors"]


def test_withdraw_consultation(client):
    c = create(client, login(client, "hospital1"))
    url = f"/api/v1/consultations/{c['id']}"
    assert client.post(url + "/withdraw", headers=login(client, "hospital2")).status_code == 403
    assert client.post(url + "/withdraw", headers=login(client, "ravi")).status_code == 403
    doctor = login(client, "hospital1")
    assert client.post(url + "/withdraw", headers=doctor).json()["status"] == "entered-in-error"
    assert client.post(url + "/withdraw", headers=doctor).status_code == 409
    # The patient still sees it, clearly marked, and the FHIR document says so too
    ravi = login(client, "ravi")
    assert client.get(url, headers=ravi).json()["status"] == "entered-in-error"
    data = client.get(url + "/fhir", headers=ravi).json()
    assert data["validation"]["valid"], data["validation"]["errors"]
    assert data["resource"]["entry"][0]["resource"]["status"] == "entered-in-error"
    events = [e["event_type"] for e in client.get("/api/v1/audit-events", headers=login(client, "admin")).json()]
    assert {"CONSULTATION_CREATED", "CONSULTATION_WITHDRAWN"} <= set(events)


def test_seeded_consultation_visible_to_asha(client):
    asha = login(client, "asha")
    items = client.get("/api/v1/consultations", headers=asha).json()
    assert [x["diagnosis"] for x in items] == ["Acute pharyngitis"]
    data = client.get(f"/api/v1/consultations/{items[0]['id']}/fhir", headers=asha).json()
    assert data["validation"]["valid"], data["validation"]["errors"]
