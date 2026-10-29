import os
import tempfile
from datetime import timedelta

# Point the app at a throw-away database BEFORE the app is imported.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, utcnow  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import SAMPLE_PASSWORD, seed  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    with TestClient(app) as c:
        yield c


def login(client, username, password=SAMPLE_PASSWORD):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


CBC = [
    {"test_name": "Hemoglobin", "loinc_code": "718-7", "value": 13.5, "unit": "g/dL", "ref_low": 12, "ref_high": 15.5},
    {"test_name": "WBC", "loinc_code": "6690-2", "value": 11.8, "unit": "10*3/uL", "ref_low": 4, "ref_high": 11},
    {"test_name": "Platelets", "loinc_code": "777-3", "value": 250, "unit": "10*3/uL", "ref_low": 150, "ref_high": 410},
]


def create_cbc(client, headers, patient_id=1):
    body = {"patient_id": patient_id, "title": "Complete Blood Count", "panel_loinc_code": "58410-2",
            "collected_at": (utcnow() - timedelta(hours=2)).isoformat(), "observations": CBC}
    r = client.post("/api/v1/reports", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def request_access(client, headers, report_id, purpose="TREAT"):
    r = client.post("/api/v1/access-requests", json={"report_id": report_id, "purpose": purpose}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
