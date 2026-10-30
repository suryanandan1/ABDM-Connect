# Mock ABDM Server (for learning)

A small local server that **pretends to be ABDM** so you can build and test ABHA-based patient
registration without sandbox credentials. **It is not ABDM.** Paths and payloads are modelled loosely
on the ABDM sandbox (gateway session + ABHA v3 profile login). Check the official sandbox docs
before writing code for real ABDM.

## Run it

```powershell
cd mock_abdm
..\backend\.venv\Scripts\python -m uvicorn server:app --port 9000 --reload
```

Interactive API docs: http://localhost:9000/docs · Test identities: http://localhost:9000/mock/holders

Default credentials (override with `MOCK_ABDM_CLIENT_ID` / `MOCK_ABDM_CLIENT_SECRET`):
`SBX_MOCK_001` / `mock-secret-change-me`

## The flow

| # | Call | You send | You get |
|---|---|---|---|
| 1 | `POST /gateway/v0.5/sessions` | `clientId`, `clientSecret` | `accessToken` (20 min) |
| 2 | `POST /v3/profile/login/request/otp` | `abhaNumber` **or** `abhaAddress` | `txnId`; the OTP is printed in the server terminal as `[MOCK SMS]` |
| 3 | `POST /v3/profile/login/verify` | `txnId`, `otp` | `token` (the patient's X-token, 30 min) |
| 4 | `GET /v3/profile/account` | header `X-token: Bearer <token>` | verified ABHA profile |

Calls 2–4 need these headers, as real ABDM calls do:

```
Authorization: Bearer <accessToken>
REQUEST-ID:    <a new UUID for every call>
TIMESTAMP:     <current time, ISO 8601 UTC>
```

## Rules it enforces

- OTP expires after **5 minutes**; **3 wrong attempts** lock the transaction; an OTP works **once**.
- Unknown ABHA → `404`, badly formatted ABHA → `400`, deactivated ABHA (`91-0000-1111-2222`) → `403`.
- Errors look like `{"error": {"code": "MOCK-…", "message": "…"}}`. The codes are invented for this mock.
- State is in memory, so restarting the server clears tokens and OTPs.

## Test identities

Edit `holders.json` to add your own.

| ABHA number | ABHA address | Name | Use it to try |
|---|---|---|---|
| 91-1111-2222-3333 | ravi.kumar@sbx | Ravi Kumar, born 1990 | New patient. Same name as the app's seeded Ravi but a different birth date, so it is a different person |
| 91-4444-5555-6666 | priya.sharma@sbx | Priya Sharma | New patient |
| 91-7777-8888-9999 | arjun.singh@sbx | Arjun Pal Singh | Middle name |
| 91-2222-3333-4444 | asha.verma@sbx | Asha Verma | **Link** to the app's seeded PAT-000001 (same name + birth date) |
| 91-3333-4444-5555 | ravi.kumar85@sbx | Ravi Kumar, born 1985 | **Link** to the app's seeded PAT-000002 (same name + birth date) |
| 91-5555-6666-7777 | lakshmi@sbx | Lakshmi | Single name (no surname), elderly patient (born 1952) |
| 91-6666-7777-8888 | aarav.mehta@sbx | Aarav Mehta | Child (born 2019) |
| 91-8888-9999-0000 | sam.dsouza@sbx | Sam D'Souza | Gender "other", apostrophe in the name |
| 91-1212-3434-5656 | *(none)* | Fatima Begum | No ABHA address: only the ABHA number works |
| 91-9090-8080-7070 | neha.gupta@sbx | Neha Gupta, born 1992 | Two people with the same name … |
| 91-9191-8181-7171 | neha.gupta99@sbx | Neha Rani Gupta, born 1999 | … and different birth dates: both register separately |
| 91-2020-3030-4040 | vikram.reddy@sbx | Vikram Reddy | **Locked** ABHA: OTP request is refused |
| 91-0000-1111-2222 | deactivated.user@sbx | Meena Iyer | **Deactivated** ABHA: OTP request is refused |

Patients get the OTP "SMS" on the mobile listed by `GET /mock/holders`.

## Tests

```powershell
cd mock_abdm
..\backend\.venv\Scripts\python -m pytest -q
```

## Not simulated yet

RSA encryption of the ABHA number and OTP (real ABDM v3 requires it), ABHA creation, Scan & Share,
care-context linking and consent flows.
