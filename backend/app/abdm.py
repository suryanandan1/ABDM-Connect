"""Client for the ABDM ABHA verification flow (M1).

Today ABDM_BASE_URL points at the local mock server in ../mock_abdm. The calls are modelled on the
ABDM sandbox (gateway session + ABHA v3 profile login) but real ABDM additionally needs RSA-encrypted
ABHA numbers and OTPs; check the official sandbox docs before switching the URL to real ABDM.

Every call carries the gateway token plus a fresh REQUEST-ID and TIMESTAMP header.
"""
import threading
import uuid
from datetime import timedelta

import httpx

from .config import ABDM_BASE_URL, ABDM_CLIENT_ID, ABDM_CLIENT_SECRET, ABDM_TIMEOUT_SECONDS
from .database import utcnow

GENDERS = {"M": "male", "F": "female", "O": "other"}


class AbdmError(Exception):
    """An ABDM call failed. `status` is what our API should answer (never 401: that logs our user out)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def http_client() -> httpx.Client:
    """Separate function so tests can swap in the mock server running in-process."""
    return httpx.Client(base_url=ABDM_BASE_URL, timeout=ABDM_TIMEOUT_SECONDS)


_session = {"token": None, "expires_at": None}
_session_lock = threading.Lock()


def reset_session():
    _session.update(token=None, expires_at=None)


def _gateway_token(client: httpx.Client) -> str:
    with _session_lock:
        if _session["token"] and _session["expires_at"] > utcnow():
            return _session["token"]
        r = client.post("/gateway/v0.5/sessions", json={"clientId": ABDM_CLIENT_ID, "clientSecret": ABDM_CLIENT_SECRET})
        if r.status_code != 200:
            raise AbdmError(502, "ABDM rejected this application's client credentials. Check ABDM_CLIENT_ID / ABDM_CLIENT_SECRET.")
        body = r.json()
        # Renew a minute early so a token never expires mid-request.
        _session.update(token=body["accessToken"],
                        expires_at=utcnow() + timedelta(seconds=max(body.get("expiresIn", 600) - 60, 0)))
        return _session["token"]


def _call(method: str, path: str, json=None, headers=None) -> dict:
    try:
        with http_client() as client:
            for attempt in (1, 2):
                h = {
                    "Authorization": f"Bearer {_gateway_token(client)}",
                    "REQUEST-ID": str(uuid.uuid4()),
                    "TIMESTAMP": utcnow().isoformat().replace("+00:00", "Z"),
                    **(headers or {}),
                }
                r = client.request(method, path, json=json, headers=h)
                if r.status_code == 401 and attempt == 1 and "X-token" not in (headers or {}):
                    reset_session()  # gateway token expired early or server restarted: get a new one, retry once
                    continue
                break
    except httpx.HTTPError:
        raise AbdmError(503, "ABDM service is unreachable. Is the mock ABDM server running on port 9000?") from None

    if r.status_code < 400:
        return r.json()
    try:
        message = r.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = f"ABDM returned an error ({r.status_code})"
    status = r.status_code if r.status_code in (400, 403, 404, 429) else 502
    raise AbdmError(status, message)


def request_otp(abha_number: str | None = None, abha_address: str | None = None) -> dict:
    """ABDM sends an OTP to the patient's linked mobile. Returns {"txnId", "message"}."""
    body = {"abhaNumber": abha_number} if abha_number else {"abhaAddress": abha_address}
    return _call("POST", "/v3/profile/login/request/otp", json=body)


def verify_otp_and_get_profile(txn_id: str, otp: str) -> dict:
    """Verify the OTP the patient read out, then fetch their verified ABHA profile."""
    token = _call("POST", "/v3/profile/login/verify", json={"txnId": txn_id, "otp": otp})["token"]
    profile = _call("GET", "/v3/profile/account", headers={"X-token": f"Bearer {token}"})
    return {
        "abha_number": profile["abhaNumber"],
        "abha_address": profile.get("abhaAddress") or None,
        "full_name": profile.get("name") or " ".join(
            p for p in (profile.get("firstName"), profile.get("middleName"), profile.get("lastName")) if p),
        "gender": GENDERS.get(profile.get("gender"), "unknown"),
        "birth_date": profile["dateOfBirth"],
        "phone": profile.get("mobile") or None,
    }
