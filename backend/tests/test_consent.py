from datetime import timedelta

from conftest import create_cbc, login, request_access

from app.database import SessionLocal, utcnow
from app.models import Consent


def setup_request(client):
    report = create_cbc(client, login(client, "lab1"), patient_id=1)
    hospital = login(client, "hospital1")
    req = request_access(client, hospital, report["id"])
    return report, hospital, req


def retrieve(client, headers, req, purpose="TREAT"):
    return client.post(f"/api/v1/access-requests/{req['id']}/retrieve", json={"purpose": purpose}, headers=headers)


def test_full_flow_approve_retrieve_revoke(client):
    report, hospital, req = setup_request(client)
    assert req["status"] == "PENDING"
    # Pending: no access
    assert retrieve(client, hospital, req).status_code == 403
    patient = login(client, "asha")
    approved = client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=patient).json()
    assert approved["status"] == "ACTIVE" and approved["expires_at"]
    r = retrieve(client, hospital, req)
    assert r.status_code == 200
    assert r.json()["report"]["id"] == report["id"] and r.json()["fhir"]["validation"]["valid"]
    # Revoke -> access stops immediately
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/revoke", headers=patient).json()["status"] == "REVOKED"
    denied = retrieve(client, hospital, req)
    assert denied.status_code == 403 and "REVOKED" in denied.json()["detail"]
    # Audit log has the successful and the denied retrieval
    events = client.get("/api/v1/audit-events?event_type=REPORT_RETRIEVE", headers=login(client, "admin")).json()
    assert {e["outcome"] for e in events} == {"SUCCESS", "DENIED"}
    # The patient can see their own access history
    mine = client.get("/api/v1/audit-events", headers=patient).json()
    assert {"ACCESS_REQUESTED", "CONSENT_APPROVED", "CONSENT_REVOKED", "REPORT_RETRIEVE"} <= {e["event_type"] for e in mine}


def test_deny(client):
    _, hospital, req = setup_request(client)
    patient = login(client, "asha")
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/deny", headers=patient).json()["status"] == "DENIED"
    assert retrieve(client, hospital, req).status_code == 403
    # A denied consent can't be approved or revoked afterwards
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=patient).status_code == 409
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/revoke", headers=patient).status_code == 409
    # The hospital may ask again after a denial
    assert request_access(client, hospital, req["report"]["id"])["status"] == "PENDING"


def test_invalid_transitions(client):
    _, _, req = setup_request(client)
    patient = login(client, "asha")
    cid = req["consent"]["id"]
    assert client.post(f"/api/v1/consents/{cid}/revoke", headers=patient).status_code == 409  # pending -> revoked
    client.post(f"/api/v1/consents/{cid}/approve", headers=patient)
    assert client.post(f"/api/v1/consents/{cid}/approve", headers=patient).status_code == 409  # twice
    assert client.post(f"/api/v1/consents/{cid}/deny", headers=patient).status_code == 409
    assert client.post("/api/v1/consents/9999/approve", headers=patient).status_code == 404


def test_expired_consent_blocks_access(client):
    _, hospital, req = setup_request(client)
    patient = login(client, "asha")
    client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=patient)
    assert retrieve(client, hospital, req).status_code == 200
    # Move the expiry time into the past
    db = SessionLocal()
    consent = db.get(Consent, req["consent"]["id"])
    consent.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()
    r = retrieve(client, hospital, req)
    assert r.status_code == 403 and "EXPIRED" in r.json()["detail"]
    assert client.get(f"/api/v1/consents/{req['consent']['id']}", headers=patient).json()["status"] == "EXPIRED"
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/revoke", headers=patient).status_code == 409


def test_other_patient_cannot_decide(client):
    _, _, req = setup_request(client)
    ravi = login(client, "ravi")
    assert client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=ravi).status_code == 404
    assert client.get(f"/api/v1/consents/{req['consent']['id']}", headers=ravi).status_code == 404
    assert client.get("/api/v1/consents", headers=ravi).json() == []
    events = client.get("/api/v1/audit-events?event_type=CONSENT_APPROVED&outcome=DENIED",
                        headers=login(client, "admin")).json()
    assert len(events) == 1


def test_cross_facility_hospital_cannot_retrieve(client):
    _, _, req = setup_request(client)
    client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=login(client, "asha"))
    other = login(client, "hospital2")
    r = retrieve(client, other, req)
    assert r.status_code == 403 and "another facility" in r.json()["detail"]
    assert client.get(f"/api/v1/access-requests/{req['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/access-requests", headers=other).json() == []


def test_purpose_must_match(client):
    _, hospital, req = setup_request(client)
    client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=login(client, "asha"))
    r = retrieve(client, hospital, req, purpose="HRESCH")
    assert r.status_code == 403 and "purpose" in r.json()["detail"]
    assert retrieve(client, hospital, req, purpose="NOPE").status_code == 422


def test_consent_scope_is_one_report(client):
    lab = login(client, "lab1")
    first = create_cbc(client, lab)
    hospital = login(client, "hospital1")
    req = request_access(client, hospital, first["id"])
    client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=login(client, "asha"))
    # The approved consent does not open other reports, even of the same patient.
    assert client.get("/api/v1/reports/1", headers=hospital).status_code == 403
    assert retrieve(client, hospital, req).json()["report"]["id"] == first["id"]


def test_duplicate_and_invalid_requests(client):
    _, hospital, req = setup_request(client)
    r = client.post("/api/v1/access-requests", json={"report_id": req["report"]["id"], "purpose": "TREAT"}, headers=hospital)
    assert r.status_code == 409
    assert client.post("/api/v1/access-requests", json={"report_id": 999, "purpose": "TREAT"}, headers=hospital).status_code == 404
    bad = client.post("/api/v1/access-requests", json={"report_id": 1, "purpose": "TREAT", "duration_days": 99},
                      headers=hospital)
    assert bad.status_code == 422
    assert client.post("/api/v1/access-requests/999/retrieve", json={"purpose": "TREAT"}, headers=hospital).status_code == 404
    # Labs cannot request access or retrieve
    lab = login(client, "lab1")
    assert client.post("/api/v1/access-requests", json={"report_id": 1, "purpose": "TREAT"}, headers=lab).status_code == 403
    assert retrieve(client, lab, req).status_code == 403
