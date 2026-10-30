"""Mock ABDM server for learning: simulates the ABHA verification (M1) flow on localhost.

This is NOT ABDM. Paths and payloads are modelled loosely on the ABDM sandbox (gateway session +
ABHA v3 profile login) so the client code you write against it looks similar, but always check the
official sandbox docs before pointing real code at real ABDM.

Flow:
  1. POST /gateway/v0.5/sessions                  clientId + clientSecret  -> accessToken
  2. POST /v3/profile/login/request/otp           abhaNumber/abhaAddress   -> txnId  (OTP printed here)
  3. POST /v3/profile/login/verify                txnId + otp              -> X-token for that patient
  4. GET  /v3/profile/account                     X-token                  -> verified ABHA profile

Run:  uvicorn server:app --port 9000 --reload   (from the mock_abdm folder)
"""
import json
import os
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

CLIENT_ID = os.getenv("MOCK_ABDM_CLIENT_ID", "SBX_MOCK_001")
CLIENT_SECRET = os.getenv("MOCK_ABDM_CLIENT_SECRET", "mock-secret-change-me")
SESSION_TTL = timedelta(minutes=20)
OTP_TTL = timedelta(minutes=5)
X_TOKEN_TTL = timedelta(minutes=30)
MAX_OTP_ATTEMPTS = 3
HOLDERS_FILE = Path(__file__).with_name("holders.json")


def now() -> datetime:
    return datetime.now(UTC)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalise_abha_number(value: str) -> str | None:
    """Accept 14 digits with or without hyphens; return the 91-XXXX-XXXX-XXXX form."""
    digits = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{14}", digits):
        return None
    return f"{digits[:2]}-{digits[2:6]}-{digits[6:10]}-{digits[10:]}"


# --- In-memory state (reset on restart, like a fresh sandbox) ------------------------------------

@dataclass
class OtpTransaction:
    abha_number: str
    otp: str
    expires_at: datetime
    attempts: int = 0
    used: bool = False


@dataclass
class State:
    holders: dict[str, dict] = field(default_factory=dict)      # abhaNumber -> profile
    sessions: dict[str, datetime] = field(default_factory=dict)  # accessToken -> expiry
    transactions: dict[str, OtpTransaction] = field(default_factory=dict)  # txnId -> txn
    x_tokens: dict[str, tuple[str, datetime]] = field(default_factory=dict)  # X-token -> (abhaNumber, expiry)

    def reset(self):
        self.holders = {h["abhaNumber"]: h for h in json.loads(HOLDERS_FILE.read_text(encoding="utf-8"))}
        self.sessions.clear()
        self.transactions.clear()
        self.x_tokens.clear()

    def find_holder(self, abha_number: str | None, abha_address: str | None) -> dict | None:
        if abha_number:
            normalised = normalise_abha_number(abha_number)
            return self.holders.get(normalised) if normalised else None
        if abha_address:
            address = abha_address.strip().lower()
            return next((h for h in self.holders.values() if h["abhaAddress"] == address), None)
        return None


state = State()
state.reset()

app = FastAPI(
    title="Mock ABDM Server",
    description="Local simulation of ABDM gateway + ABHA verification for learning. Not ABDM.",
    version="0.1.0",
)


class MockAbdmError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(MockAbdmError)
def _abdm_error(_request: Request, exc: MockAbdmError):
    # Error codes are invented for this mock; real ABDM uses its own codes.
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


# --- Common request checks -------------------------------------------------------------------------

def require_gateway_headers(
    request_id: str | None = Header(None, alias="REQUEST-ID"),
    timestamp: str | None = Header(None, alias="TIMESTAMP"),
):
    """Real ABDM calls carry a unique request id and a timestamp; make clients learn to send them."""
    if not request_id or not timestamp:
        raise MockAbdmError(400, "MOCK-400", "REQUEST-ID and TIMESTAMP headers are required")
    try:
        uuid.UUID(request_id)
    except ValueError:
        raise MockAbdmError(400, "MOCK-400", "REQUEST-ID must be a UUID") from None


def require_session(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise MockAbdmError(401, "MOCK-401", "Missing gateway access token")
    expiry = state.sessions.get(authorization.removeprefix("Bearer "))
    if expiry is None or expiry < now():
        raise MockAbdmError(401, "MOCK-401", "Gateway access token is invalid or expired")


# --- 1. Gateway session ----------------------------------------------------------------------------

class SessionRequest(BaseModel):
    clientId: str
    clientSecret: str


@app.post("/gateway/v0.5/sessions")
def create_session(body: SessionRequest):
    if not (secrets.compare_digest(body.clientId, CLIENT_ID) and secrets.compare_digest(body.clientSecret, CLIENT_SECRET)):
        raise MockAbdmError(401, "MOCK-401", "Invalid client credentials")
    token = secrets.token_urlsafe(32)
    state.sessions[token] = now() + SESSION_TTL
    return {"accessToken": token, "expiresIn": int(SESSION_TTL.total_seconds()), "tokenType": "bearer"}


# --- 2. Request OTP --------------------------------------------------------------------------------

class OtpRequest(BaseModel):
    abhaNumber: str | None = None
    abhaAddress: str | None = None


@app.post("/v3/profile/login/request/otp", dependencies=[Depends(require_session), Depends(require_gateway_headers)])
def request_otp(body: OtpRequest):
    if not body.abhaNumber and not body.abhaAddress:
        raise MockAbdmError(400, "MOCK-400", "Send abhaNumber or abhaAddress")
    if body.abhaNumber and normalise_abha_number(body.abhaNumber) is None:
        raise MockAbdmError(400, "MOCK-400", "ABHA number must be 14 digits")
    holder = state.find_holder(body.abhaNumber, body.abhaAddress)
    if holder is None:
        raise MockAbdmError(404, "MOCK-404", "No ABHA found for the given identifier")
    if holder["status"] != "ACTIVE":
        raise MockAbdmError(403, "MOCK-403", "This ABHA is not active")

    txn_id = str(uuid.uuid4())
    otp = generate_otp()
    state.transactions[txn_id] = OtpTransaction(holder["abhaNumber"], otp, now() + OTP_TTL)
    # This print is the "SMS". In real ABDM the OTP goes to the patient's phone and is never returned.
    print(f"\n[MOCK SMS] to {holder['mobile']}: your ABHA OTP is {otp} (txnId {txn_id})\n", flush=True)
    return {"txnId": txn_id, "message": f"OTP sent to mobile ending {holder['mobile'][-4:]}"}


# --- 3. Verify OTP ---------------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    txnId: str
    otp: str


@app.post("/v3/profile/login/verify", dependencies=[Depends(require_session), Depends(require_gateway_headers)])
def verify_otp(body: VerifyRequest):
    txn = state.transactions.get(body.txnId)
    if txn is None or txn.used:
        raise MockAbdmError(400, "MOCK-TXN", "Unknown or already used transaction")
    if txn.expires_at < now():
        raise MockAbdmError(400, "MOCK-OTP-EXPIRED", "OTP expired, request a new one")
    if txn.attempts >= MAX_OTP_ATTEMPTS:
        raise MockAbdmError(429, "MOCK-OTP-LOCKED", "Too many wrong attempts, request a new OTP")
    if not secrets.compare_digest(body.otp, txn.otp):
        txn.attempts += 1
        left = MAX_OTP_ATTEMPTS - txn.attempts
        raise MockAbdmError(400, "MOCK-OTP-INVALID", f"Incorrect OTP, {left} attempt(s) left")

    txn.used = True
    x_token = secrets.token_urlsafe(32)
    state.x_tokens[x_token] = (txn.abha_number, now() + X_TOKEN_TTL)
    return {"message": "OTP verified", "token": x_token, "expiresIn": int(X_TOKEN_TTL.total_seconds())}


# --- 4. Fetch profile ------------------------------------------------------------------------------

@app.get("/v3/profile/account", dependencies=[Depends(require_session), Depends(require_gateway_headers)])
def get_profile(x_token: str | None = Header(None, alias="X-token")):
    entry = state.x_tokens.get((x_token or "").removeprefix("Bearer "))
    if entry is None or entry[1] < now():
        raise MockAbdmError(401, "MOCK-401", "X-token is invalid or expired")
    holder = state.holders[entry[0]]
    name = " ".join(p for p in (holder["firstName"], holder["middleName"], holder["lastName"]) if p)
    return {**holder, "name": name}


# --- Learning helpers (would never exist on real ABDM) ---------------------------------------------

@app.get("/mock/holders")
def list_holders():
    """Test identities you can use; mobile is shown so you know where the 'SMS' would go."""
    return [{k: h[k] for k in ("abhaNumber", "abhaAddress", "firstName", "lastName", "mobile", "status")}
            for h in state.holders.values()]


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-abdm"}
