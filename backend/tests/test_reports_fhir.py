from conftest import CBC, create_cbc, login

from app import fhir


def test_register_patient_and_patient_login(client):
    lab = login(client, "lab1")
    body = {"full_name": "Neha Singh", "gender": "female", "birth_date": "1995-03-21", "phone": "9000000099",
            "username": "neha", "password": "NehaPass1"}
    r = client.post("/api/v1/patients", json=body, headers=lab)
    assert r.status_code == 201
    assert r.json()["patient_code"].startswith("PAT-")
    # Duplicate name + birth date is refused
    assert client.post("/api/v1/patients", json={**body, "username": "neha2"}, headers=lab).status_code == 409
    # The new patient can log in and sees only their own record
    me = login(client, "neha", "NehaPass1")
    assert [p["full_name"] for p in client.get("/api/v1/patients", headers=me).json()] == ["Neha Singh"]
    assert client.get("/api/v1/patients/1", headers=me).status_code == 404


def test_patient_validation_errors(client):
    lab = login(client, "lab1")
    bad = {"full_name": "A", "gender": "robot", "birth_date": "2999-01-01", "username": "a", "password": "short"}
    r = client.post("/api/v1/patients", json=bad, headers=lab)
    assert r.status_code == 422
    assert {e["loc"][-1] for e in r.json()["detail"]} >= {"full_name", "gender", "birth_date", "username", "password"}


def test_create_report_uses_loinc_display_and_interpretation(client):
    report = create_cbc(client, login(client, "lab1"))
    obs = {o["loinc_code"]: o for o in report["observations"]}
    assert obs["718-7"]["loinc_display"] == "Hemoglobin [Mass/volume] in Blood"
    assert obs["6690-2"]["interpretation"] == "H"
    assert obs["777-3"]["interpretation"] == "N"


def test_report_validation(client):
    lab = login(client, "lab1")
    base = {"patient_id": 1, "title": "CBC", "collected_at": "2020-01-01T10:00:00Z"}
    unknown_code = {**base, "observations": [{**CBC[0], "loinc_code": "99999-9"}]}
    r = client.post("/api/v1/reports", json=unknown_code, headers=lab)
    assert r.status_code == 422 and "not a known test code" in r.json()["detail"][0]
    duplicate = {**base, "observations": [CBC[0], CBC[0]]}
    assert client.post("/api/v1/reports", json=duplicate, headers=lab).status_code == 422
    bad_range = {**base, "observations": [{**CBC[0], "ref_low": 20, "ref_high": 10}]}
    assert client.post("/api/v1/reports", json=bad_range, headers=lab).status_code == 422
    bad_unit = {**base, "observations": [{**CBC[0], "unit": "bananas"}]}
    assert client.post("/api/v1/reports", json=bad_unit, headers=lab).status_code == 422
    future = {**base, "collected_at": "2999-01-01T10:00:00Z", "observations": [CBC[0]]}
    assert client.post("/api/v1/reports", json=future, headers=lab).status_code == 422
    empty = {**base, "observations": []}
    assert client.post("/api/v1/reports", json=empty, headers=lab).status_code == 422
    no_patient = {**base, "patient_id": 999, "observations": [CBC[0]]}
    assert client.post("/api/v1/reports", json=no_patient, headers=lab).status_code == 404


def test_cross_facility_lab_cannot_read_report(client):
    report = create_cbc(client, login(client, "lab1"))
    lab2 = login(client, "lab2")
    assert client.get(f"/api/v1/reports/{report['id']}", headers=lab2).status_code == 403
    assert client.get(f"/api/v1/reports/{report['id']}/fhir", headers=lab2).status_code == 403
    assert client.get(f"/api/v1/patients/1/reports", headers=lab2).json() == []


def test_patient_reads_own_report_but_not_others(client):
    report = create_cbc(client, login(client, "lab1"), patient_id=1)
    assert client.get(f"/api/v1/reports/{report['id']}", headers=login(client, "asha")).status_code == 200
    assert client.get(f"/api/v1/reports/{report['id']}", headers=login(client, "ravi")).status_code == 403


def test_hospital_and_admin_cannot_read_report_directly(client):
    report = create_cbc(client, login(client, "lab1"))
    for user in ("hospital1", "admin"):
        h = login(client, user)
        assert client.get(f"/api/v1/reports/{report['id']}", headers=h).status_code == 403
        assert client.get(f"/api/v1/fhir/DiagnosticReport/{report['id']}", headers=h).status_code == 403


def test_fhir_bundle_is_valid_r4(client):
    lab = login(client, "lab1")
    report = create_cbc(client, lab)
    r = client.get(f"/api/v1/reports/{report['id']}/fhir", headers=lab).json()
    assert r["validation"] == {**r["validation"], "valid": True, "errors": []}
    bundle = r["resource"]
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert bundle["type"] == "document" and types[0] == "Composition"
    assert types.count("Observation") == 3 and {"Patient", "Organization", "Practitioner", "DiagnosticReport"} <= set(types)
    hb = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation")
    assert hb["code"]["coding"][0] == {"system": "http://loinc.org", "code": "718-7",
                                       "display": "Hemoglobin [Mass/volume] in Blood"}
    assert hb["valueQuantity"]["system"] == "http://unitsofmeasure.org"


def test_fhir_read_endpoints(client):
    lab = login(client, "lab1")
    report = create_cbc(client, lab)
    dr = client.get(f"/api/v1/fhir/DiagnosticReport/{report['id']}", headers=lab)
    assert dr.headers["content-type"].startswith("application/fhir+json")
    assert len(dr.json()["result"]) == 3
    obs_id = report["observations"][0]["id"]
    assert client.get(f"/api/v1/fhir/Observation/{obs_id}", headers=lab).json()["resourceType"] == "Observation"
    p = client.get("/api/v1/fhir/Patient/1", headers=lab).json()
    assert p["identifier"][0]["value"] == "PAT-000001"
    assert fhir.validate(p) == []
    meta = client.get("/api/v1/fhir/metadata").json()
    assert meta["fhirVersion"] == "4.0.1" and fhir.validate(meta) == []


def test_validator_reports_errors():
    broken = {"resourceType": "Observation", "code": {"text": "x"}, "valueQuantity": {"value": "abc"}, "foo": 1}
    errors = fhir.validate(broken)
    assert any("status" in e for e in errors) and any("foo" in e for e in errors)
    bundle = {"resourceType": "Bundle", "type": "document", "entry": [
        {"resource": {"resourceType": "Observation", "id": "1", "status": "final", "code": {"text": "x"},
                      "subject": {"reference": "Patient/9"}}}]}
    assert any("not in the bundle" in e for e in fhir.validate(bundle))


def test_loinc_search(client):
    lab = login(client, "lab1")
    assert client.get("/api/v1/loinc/search?q=Hb", headers=lab).json()[0]["code"] == "718-7"
    assert client.get("/api/v1/loinc/search?q=718-7", headers=lab).json()[0]["code"] == "718-7"
    assert client.get("/api/v1/loinc/search?q=glucose", headers=lab).json()[0]["display"].startswith("Glucose")
    assert client.get("/api/v1/loinc/search?q=cbc&kind=panel", headers=lab).json()[0]["code"] == "58410-2"
    assert client.get("/api/v1/loinc/search?q=zzzz", headers=lab).json() == []
    assert client.get("/api/v1/loinc/search?q=hb", headers=login(client, "hospital1")).status_code == 403


def test_withdrawn_report_hidden_from_hospital(client):
    lab = login(client, "lab1")
    report = create_cbc(client, lab)
    assert client.post(f"/api/v1/reports/{report['id']}/withdraw", headers=lab).json()["status"] == "entered-in-error"
    hospital = login(client, "hospital1")
    ids = [r["id"] for r in client.get("/api/v1/patients/1/reports", headers=hospital).json()]
    assert report["id"] not in ids
    r = client.post("/api/v1/access-requests", json={"report_id": report["id"], "purpose": "TREAT"}, headers=hospital)
    assert r.status_code == 404
