"""ABHA registration against the real mock ABDM server (../mock_abdm), run in-process."""
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import abdm
from conftest import login

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mock_abdm"))
import server as mock_abdm  # noqa: E402

OTP = "123456"
RAVI = "91-1111-2222-3333"  # not in the app yet (the seeded Ravi Kumar has another birth date)
ASHA = "91-2222-3333-4444"  # same name and birth date as seeded PAT-000001


@pytest.fixture(autouse=True)
def mock_server(monkeypatch):
    mock_abdm.state.reset()
    abdm.reset_session()
    monkeypatch.setattr(mock_abdm, "generate_otp", lambda: OTP)
    monkeypatch.setattr(abdm, "http_client", lambda: TestClient(mock_abdm.app))


def verify(client, h, abha=RAVI, otp=OTP):
    r = client.post("/api/v1/patients/abha/init", headers=h, json={"abha_number": abha})
    assert r.status_code == 200, r.text
    return client.post("/api/v1/patients/abha/verify", headers=h, json={"txn_id": r.json()["txn_id"], "otp": otp})


def test_register_new_patient_with_abha(client):
    h = login(client, "lab1")
    r = verify(client, h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["full_name"] == "Ravi Kumar" and body["profile"]["gender"] == "male"
    assert body["existing_patient"] is None and body["possible_match"] is None

    r = client.post("/api/v1/patients/abha/register", headers=h,
                    json={"abha_token": body["abha_token"], "username": "ravi.abha", "password": "Temp@12345"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["abha_number"] == RAVI and p["abha_address"] == "ravi.kumar@sbx" and p["abha_verified_at"]
    assert p["birth_date"] == "1990-04-12" and p["phone"] == "9800000001"

    # Searchable by ABHA, and shown in FHIR.
    assert [x["id"] for x in client.get("/api/v1/patients?q=2222-3333", headers=h).json()] == [p["id"]]
    fhir = client.get(f"/api/v1/fhir/Patient/{p['id']}", headers=h).json()
    assert RAVI in [i["value"] for i in fhir["identifier"]]

    # The same ABHA again is recognised, not duplicated.
    again = verify(client, h).json()
    assert again["existing_patient"]["id"] == p["id"]
    r = client.post("/api/v1/patients/abha/register", headers=h,
                    json={"abha_token": again["abha_token"], "username": "ravi.two", "password": "Temp@12345"})
    assert r.status_code == 409


def test_link_abha_to_existing_patient(client):
    h = login(client, "lab1")
    body = verify(client, h, abha=ASHA).json()
    assert body["possible_match"]["patient_code"] == "PAT-000001"

    r = client.post("/api/v1/patients/abha/register", headers=h,
                    json={"abha_token": body["abha_token"], "username": "asha2", "password": "Temp@12345"})
    assert r.status_code == 409 and "Link" in r.json()["detail"]

    assert client.post("/api/v1/patients/2/abha", headers=h, json={"abha_token": body["abha_token"]}).status_code == 409
    r = client.post("/api/v1/patients/1/abha", headers=h, json={"abha_token": body["abha_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["abha_number"] == ASHA


def test_wrong_otp_and_unknown_abha(client):
    h = login(client, "lab1")
    r = verify(client, h, otp="000000")
    assert r.status_code == 400 and "attempt" in r.json()["detail"]
    r = client.post("/api/v1/patients/abha/init", headers=h, json={"abha_number": "91-9999-9999-9999"})
    assert r.status_code == 404
    events = client.get("/api/v1/audit-events?event_type=ABHA_OTP_REQUESTED", headers=login(client, "admin")).json()
    assert {e["outcome"] for e in events} == {"SUCCESS", "FAILURE"}


@pytest.mark.parametrize("body", [{}, {"abha_number": "123"}, {"abha_number": RAVI, "abha_address": "ravi.kumar@sbx"}])
def test_init_validation(client, body):
    assert client.post("/api/v1/patients/abha/init", headers=login(client, "lab1"), json=body).status_code == 422


def test_abha_token_is_tied_to_the_verifying_user(client):
    token = verify(client, login(client, "lab1")).json()["abha_token"]
    r = client.post("/api/v1/patients/abha/register", headers=login(client, "lab2"),
                    json={"abha_token": token, "username": "ravi.abha", "password": "Temp@12345"})
    assert r.status_code == 400
    r = client.post("/api/v1/patients/abha/register", headers=login(client, "lab1"),
                    json={"abha_token": token + "x", "username": "ravi.abha", "password": "Temp@12345"})
    assert r.status_code == 400


def test_only_lab_staff_can_use_abha_routes(client):
    for user in ("hospital1", "asha"):
        r = client.post("/api/v1/patients/abha/init", headers=login(client, user), json={"abha_number": RAVI})
        assert r.status_code == 403


def test_mock_server_down_gives_503_not_401(client, monkeypatch):
    def unreachable():
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(abdm, "http_client", unreachable)
    r = client.post("/api/v1/patients/abha/init", headers=login(client, "lab1"), json={"abha_number": RAVI})
    assert r.status_code == 503


def test_bad_client_secret_gives_502(client, monkeypatch):
    monkeypatch.setattr(abdm, "ABDM_CLIENT_SECRET", "wrong")
    r = client.post("/api/v1/patients/abha/init", headers=login(client, "lab1"), json={"abha_number": RAVI})
    assert r.status_code == 502
