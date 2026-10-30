import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import server

OTP = "123456"


@pytest.fixture
def client(monkeypatch):
    server.state.reset()
    monkeypatch.setattr(server, "generate_otp", lambda: OTP)
    with TestClient(server.app) as c:
        yield c


def headers(client, **extra):
    r = client.post("/gateway/v0.5/sessions", json={"clientId": server.CLIENT_ID, "clientSecret": server.CLIENT_SECRET})
    assert r.status_code == 200, r.text
    return {
        "Authorization": "Bearer " + r.json()["accessToken"],
        "REQUEST-ID": str(uuid.uuid4()),
        "TIMESTAMP": datetime.now(UTC).isoformat(),
        **extra,
    }


def request_otp(client, h, **body):
    return client.post("/v3/profile/login/request/otp", headers=h, json=body)


def test_full_flow_returns_verified_profile(client):
    h = headers(client)
    r = request_otp(client, h, abhaNumber="91111122223333")  # hyphens optional
    assert r.status_code == 200, r.text
    assert "3333" not in r.json()["message"] and "0001" in r.json()["message"]
    assert "otp" not in r.json()

    r = client.post("/v3/profile/login/verify", headers=h, json={"txnId": r.json()["txnId"], "otp": OTP})
    assert r.status_code == 200, r.text

    r = client.get("/v3/profile/account", headers={**h, "X-token": "Bearer " + r.json()["token"]})
    assert r.status_code == 200, r.text
    assert r.json()["abhaNumber"] == "91-1111-2222-3333"
    assert r.json()["name"] == "Ravi Kumar"


def test_login_by_abha_address(client):
    r = request_otp(client, headers(client), abhaAddress="Priya.Sharma@sbx")
    assert r.status_code == 200, r.text


def test_wrong_client_secret_rejected(client):
    r = client.post("/gateway/v0.5/sessions", json={"clientId": server.CLIENT_ID, "clientSecret": "nope"})
    assert r.status_code == 401


def test_missing_token_and_headers_rejected(client):
    assert client.post("/v3/profile/login/request/otp", json={"abhaNumber": "91-1111-2222-3333"}).status_code == 401
    h = headers(client)
    del h["REQUEST-ID"]
    assert request_otp(client, h, abhaNumber="91-1111-2222-3333").status_code == 400


@pytest.mark.parametrize("abha, status", [("1234", 400), ("91-9999-9999-9999", 404), ("91-0000-1111-2222", 403)])
def test_bad_unknown_and_inactive_abha(client, abha, status):
    assert request_otp(client, headers(client), abhaNumber=abha).status_code == status


def test_three_wrong_otps_lock_the_transaction(client):
    h = headers(client)
    txn = request_otp(client, h, abhaNumber="91-1111-2222-3333").json()["txnId"]
    for _ in range(3):
        assert client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": "000000"}).status_code == 400
    r = client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": OTP})
    assert r.status_code == 429


def test_expired_otp_rejected(client, monkeypatch):
    h = headers(client)
    txn = request_otp(client, h, abhaNumber="91-1111-2222-3333").json()["txnId"]
    later = datetime.now(UTC) + timedelta(minutes=6)
    monkeypatch.setattr(server, "now", lambda: later)
    server.state.sessions = {k: later + timedelta(minutes=1) for k in server.state.sessions}  # keep session valid
    r = client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": OTP})
    assert r.json()["error"]["code"] == "MOCK-OTP-EXPIRED"


def test_otp_cannot_be_reused(client):
    h = headers(client)
    txn = request_otp(client, h, abhaNumber="91-1111-2222-3333").json()["txnId"]
    assert client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": OTP}).status_code == 200
    assert client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": OTP}).status_code == 400


def test_profile_needs_valid_x_token(client):
    assert client.get("/v3/profile/account", headers={**headers(client), "X-token": "Bearer fake"}).status_code == 401


@pytest.mark.parametrize("body, status", [
    ({"abhaNumber": "91-1212-3434-5656"}, 200),  # holder without an ABHA address
    ({"abhaAddress": "lakshmi@sbx"}, 200),  # single name
    ({"abhaNumber": "91-2020-3030-4040"}, 403),  # locked
])
def test_extra_identities(client, body, status):
    assert request_otp(client, headers(client), **body).status_code == status


def test_single_name_profile(client):
    h = headers(client)
    txn = request_otp(client, h, abhaAddress="lakshmi@sbx").json()["txnId"]
    token = client.post("/v3/profile/login/verify", headers=h, json={"txnId": txn, "otp": OTP}).json()["token"]
    assert client.get("/v3/profile/account", headers={**h, "X-token": f"Bearer {token}"}).json()["name"] == "Lakshmi"
