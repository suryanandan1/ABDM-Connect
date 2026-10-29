"""Hospitals as HIP and HIU: consultations shared between hospitals through patient consent."""
import os
import tempfile
from datetime import date

from conftest import create_cbc, login, request_access
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from app.database import Base, utcnow
from app import migrations as m
from app.migrations import rename_identifiers, upgrade_hip_hiu
from app.security import verify_password
from app.models import AccessRequest, Consent, Facility, Patient, Report, User


def asha_consultation_id(client):
    return client.get("/api/v1/consultations", headers=login(client, "asha")).json()[0]["id"]


def ask(client, headers, **body):
    return client.post("/api/v1/access-requests", json={"purpose": "TREAT", **body}, headers=headers)


def retrieve(client, headers, req):
    return client.post(f"/api/v1/access-requests/{req['id']}/retrieve", json={"purpose": "TREAT"}, headers=headers)


def test_hospital_requests_another_hospitals_consultation(client):
    lakeside = login(client, "hospital2")  # HIU
    # Before consent only metadata is visible: when, where and by whom - never the diagnosis
    listed = client.get("/api/v1/patients/1/consultations/other-facilities", headers=lakeside).json()
    assert len(listed) == 1 and listed[0]["facility"]["name"] == "Green Valley Hospital"
    assert "diagnosis" not in listed[0] and "chief_complaint" not in listed[0]
    cid = listed[0]["id"]
    assert client.get(f"/api/v1/consultations/{cid}", headers=lakeside).status_code == 403

    r = ask(client, lakeside, consultation_id=cid)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["report"] is None and req["consultation"]["id"] == cid and "diagnosis" not in req["consultation"]
    assert retrieve(client, lakeside, req).status_code == 403  # pending

    asha = login(client, "asha")
    consent = client.get("/api/v1/consents", headers=asha).json()[0]
    assert consent["consultation"]["doctor"]["full_name"] == "Dr. Kavita Rao" and consent["report"] is None
    client.post(f"/api/v1/consents/{consent['id']}/approve", headers=asha)

    got = retrieve(client, lakeside, req)
    assert got.status_code == 200, got.text
    assert got.json()["consultation"]["diagnosis"] == "Acute pharyngitis"
    assert got.json()["fhir"]["validation"]["valid"], got.json()["fhir"]["validation"]["errors"]

    client.post(f"/api/v1/consents/{consent['id']}/revoke", headers=asha)
    denied = retrieve(client, lakeside, req)
    assert denied.status_code == 403 and "REVOKED" in denied.json()["detail"]
    events = client.get("/api/v1/audit-events?event_type=CONSULTATION_RETRIEVE", headers=login(client, "admin")).json()
    assert {e["outcome"] for e in events} == {"SUCCESS", "DENIED"}


def test_hospital_is_hip_and_hiu_at_the_same_time(client):
    green_valley = login(client, "hospital1")
    lakeside = login(client, "hospital2")
    # Green Valley acts as HIU: it requests a lab report
    report = create_cbc(client, login(client, "lab1"))
    as_hiu = request_access(client, green_valley, report["id"])
    # ...and as HIP: Lakeside requests Green Valley's consultation
    as_hip = ask(client, lakeside, consultation_id=asha_consultation_id(client)).json()

    outgoing = [r["id"] for r in client.get("/api/v1/access-requests", headers=green_valley).json()]
    incoming = [r["id"] for r in client.get("/api/v1/access-requests/incoming", headers=green_valley).json()]
    assert outgoing == [as_hiu["id"]] and incoming == [as_hip["id"]]
    # Lakeside sees its request as outgoing only; the lab sees the report request as incoming (HIP)
    assert [r["id"] for r in client.get("/api/v1/access-requests", headers=lakeside).json()] == [as_hip["id"]]
    assert client.get("/api/v1/access-requests/incoming", headers=lakeside).json() == []
    assert [r["id"] for r in client.get("/api/v1/access-requests/incoming", headers=login(client, "lab1")).json()] == [as_hiu["id"]]
    # Patients and admins have no HIP inbox
    assert client.get("/api/v1/access-requests/incoming", headers=login(client, "asha")).status_code == 403


def test_consultation_request_rules(client):
    green_valley = login(client, "hospital1")
    lakeside = login(client, "hospital2")
    cid = asha_consultation_id(client)
    # A hospital does not request its own records
    assert ask(client, green_valley, consultation_id=cid).status_code == 409
    # Exactly one record per request
    assert ask(client, lakeside).status_code == 422
    assert ask(client, lakeside, consultation_id=cid, report_id=1).status_code == 422
    assert ask(client, lakeside, consultation_id=999).status_code == 404
    req = ask(client, lakeside, consultation_id=cid).json()
    assert ask(client, lakeside, consultation_id=cid).status_code == 409  # duplicate open request
    # Withdrawn after approval: retrieval stops and new requests are refused
    asha = login(client, "asha")
    client.post(f"/api/v1/consents/{req['consent']['id']}/approve", headers=asha)
    client.post(f"/api/v1/consultations/{cid}/withdraw", headers=green_valley)
    r = retrieve(client, lakeside, req)
    assert r.status_code == 403 and "withdrawn by the hospital" in r.json()["detail"]
    assert ask(client, login(client, "hospital2"), consultation_id=cid).status_code == 404


def test_upgrade_old_database_keeps_rows():
    """An existing database from before HIP + HIU (report_id NOT NULL, no consultation_id) is upgraded in place."""
    path = os.path.join(tempfile.mkdtemp(), "old.db").replace("\\", "/")
    eng = create_engine(f"sqlite:///{path}")
    event.listen(eng, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(eng)
    with eng.begin() as conn:  # replace the two tables with their old definitions
        conn.execute(text("DROP TABLE access_requests"))
        conn.execute(text("DROP TABLE consents"))
        conn.execute(text("""CREATE TABLE consents (
            id INTEGER NOT NULL, patient_id INTEGER NOT NULL, requester_facility_id INTEGER NOT NULL,
            report_id INTEGER NOT NULL, purpose VARCHAR(10) NOT NULL, status VARCHAR(10) NOT NULL,
            duration_days INTEGER NOT NULL, created_at DATETIME NOT NULL, decided_at DATETIME,
            expires_at DATETIME, revoked_at DATETIME, PRIMARY KEY (id),
            CHECK (status IN ('PENDING','ACTIVE','DENIED','EXPIRED','REVOKED')), CHECK (duration_days BETWEEN 1 AND 30),
            FOREIGN KEY(patient_id) REFERENCES patients (id), FOREIGN KEY(requester_facility_id) REFERENCES facilities (id),
            FOREIGN KEY(report_id) REFERENCES reports (id))"""))
        conn.execute(text("""CREATE TABLE access_requests (
            id INTEGER NOT NULL, requester_user_id INTEGER NOT NULL, requester_facility_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL, report_id INTEGER NOT NULL, purpose VARCHAR(10) NOT NULL,
            consent_id INTEGER NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id),
            FOREIGN KEY(requester_user_id) REFERENCES users (id), FOREIGN KEY(requester_facility_id) REFERENCES facilities (id),
            FOREIGN KEY(patient_id) REFERENCES patients (id), FOREIGN KEY(report_id) REFERENCES reports (id),
            UNIQUE (consent_id), FOREIGN KEY(consent_id) REFERENCES consents (id))"""))
    with Session(eng) as db:
        lab = Facility(facility_code="L", name="Lab", facility_type="LAB")
        hosp = Facility(facility_code="H", name="Hosp", facility_type="HOSPITAL")
        pat = Patient(patient_code="P", full_name="Pat", gender="female", birth_date=date(1990, 1, 1))
        user = User(username="h", password_hash="x", full_name="H", role="HOSPITAL", facility=hosp)
        report = Report(patient=pat, facility=lab, created_by=user, title="CBC", collected_at=utcnow())
        db.add_all([lab, hosp, pat, user, report])
        db.commit()
        ids = (pat.id, hosp.id, report.id, user.id)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO consents (id, patient_id, requester_facility_id, report_id, purpose, status, "
                          "duration_days, created_at) VALUES (1, :p, :h, :r, 'TREAT', 'PENDING', 7, '2026-01-01')"),
                     {"p": ids[0], "h": ids[1], "r": ids[2]})
        conn.execute(text("INSERT INTO access_requests (id, requester_user_id, requester_facility_id, patient_id, "
                          "report_id, purpose, consent_id, created_at) VALUES (1, :u, :h, :p, :r, 'TREAT', 1, '2026-01-01')"),
                     {"u": ids[3], "h": ids[1], "p": ids[0], "r": ids[2]})

    assert upgrade_hip_hiu(eng) is True
    assert upgrade_hip_hiu(eng) is False  # second run does nothing
    assert os.path.exists(path + ".bak-hip-hiu")
    with eng.connect() as conn:
        for table in ("consents", "access_requests"):
            cols = {c["name"]: c for c in inspect(conn).get_columns(table)}
            assert "consultation_id" in cols and cols["report_id"]["nullable"]
        assert conn.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    with Session(eng) as db:
        req = db.get(AccessRequest, 1)
        assert req.report_id == ids[2] and req.consent.status == "PENDING" and req.consultation_id is None
        assert db.get(Consent, 1).report.title == "CBC"
    eng.dispose()


def test_rename_identifiers_cleans_older_database():
    """Databases from earlier versions get the new column names and placeholder values cleaned."""
    path = os.path.join(tempfile.mkdtemp(), "old2.db").replace("\\", "/")
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        hosp = Facility(facility_code=m.LEGACY_PREFIX + "FAC-HOSPITAL-001", name="Hill Hospital" + m.LEGACY_NAME_SUFFIXES[1],
                        facility_type="HOSPITAL")
        taken = Facility(facility_code="FAC-LAB-002", name="River Lab", facility_type="LAB")
        clash = Facility(facility_code=m.LEGACY_PREFIX + "FAC-LAB-003", name="River Lab" + m.LEGACY_NAME_SUFFIXES[0],
                         facility_type="LAB")
        pat = Patient(patient_code=m.LEGACY_PREFIX + "PAT-000001", full_name="Pat", gender="female", birth_date=date(1990, 1, 1))
        import bcrypt
        admin = User(username="admin", full_name=m.LEGACY_ADMIN_NAME, role="ADMIN",
                     password_hash=bcrypt.hashpw(m.LEGACY_SAMPLE_PASSWORD.encode(), bcrypt.gensalt()).decode())
        other = User(username="kept", full_name="Kept", role="ADMIN",
                     password_hash=bcrypt.hashpw(b"Their-own-pass1", bcrypt.gensalt()).decode())
        db.add_all([hosp, taken, clash, pat, admin, other])
        db.commit()
    with eng.begin() as conn:  # put the old column names back
        conn.execute(text(f"ALTER TABLE patients RENAME COLUMN patient_code TO {m.LEGACY_PATIENT_COLUMN}"))
        conn.execute(text(f"ALTER TABLE facilities RENAME COLUMN facility_code TO {m.LEGACY_FACILITY_COLUMN}"))

    assert rename_identifiers(eng, "New-sample-pass1") is True
    assert rename_identifiers(eng, "New-sample-pass1") is False
    assert os.path.exists(path + ".bak-rename")
    with Session(eng) as db:
        assert db.get(Patient, 1).patient_code == "PAT-000001"
        facilities = {f.id: (f.facility_code, f.name) for f in db.query(Facility)}
        assert facilities[1] == ("FAC-HOSPITAL-001", "Hill Hospital")
        assert facilities[3][0] == "FAC-LAB-003" and facilities[3][1].startswith("River Lab ")  # name kept: would clash
        admin, other = db.query(User).filter_by(username="admin").one(), db.query(User).filter_by(username="kept").one()
        assert admin.full_name == "System Administrator" and admin.token_version == 1
        assert verify_password("New-sample-pass1", admin.password_hash)
        assert verify_password("Their-own-pass1", other.password_hash) and other.token_version == 0
    eng.dispose()
