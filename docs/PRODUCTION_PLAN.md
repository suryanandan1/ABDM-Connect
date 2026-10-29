# From test environment to real ABDM: production plan for ABDM Connect

Status: **plan only — nothing in this document is implemented yet.** Until phases 1–2 are done, the app
must keep its "Test environment" notice and must not hold real patient data.

## 1. Where the project stands today

ABDM Connect is a working simulation: labs and hospitals create FHIR R4 records, hospitals act as
both HIP and HIU, patients approve or revoke access, and everything is audited. It is **not** safe or
legal to use with real patients yet, for three separate reasons:

| Gap | Today | Why it matters |
|---|---|---|
| Security | Default JWT secret in `backend/app/config.py`; shared sample-account password (shown on the development login page); token in `sessionStorage`; no rate limiting, lockout, MFA or password policy; SQLite file with no encryption; no HTTPS enforcement; audit rows can be edited | Real health data would be exposed by any one of these |
| Identity | Local `PAT-…` IDs and `FAC-…` facility codes, staff identified only by username | Real exchange needs ABHA for patients, HFR IDs for facilities and HPR IDs for doctors |
| ABDM connection | Consent and data exchange happen inside this app only | Real HIP/HIU exchange goes through the ABDM gateway and consent manager, with encrypted data transfer and certified software |

## 2. What you must obtain (cannot be done in code)

These are prerequisites owned by you or your organisation, roughly in this order:

1. **A legal entity and a responsible person** for data protection (who signs agreements, answers
   breach notices and owns compliance).
2. **Legal advice** on the DPDP Act 2023 and DPDP Rules 2025 and on ABDM's health data policies
   (see section 8). Health data has no special category under the Act, but general consent, security and
   breach duties apply.
3. **HFR registration** (Health Facility Registry) for every real facility that will use the system.
4. **HPR registration** (Healthcare Professionals Registry) for every doctor who writes records.
5. **ABDM sandbox access**: register the software on the ABDM sandbox / bridge to receive a sandbox
   **client ID and secret**. Keep them only in `backend/.env` or a secret manager, never in the code or chat.
6. **A server with a public HTTPS address** (domain + TLS certificate). ABDM calls your HIP/HIU
   endpoints back, so a laptop on `localhost` cannot be used for integration.
7. **Terminology licences/access** as needed: LOINC (already used, check the licence terms for
   production) and SNOMED CT (India is a SNOMED member; the ABDM FHIR profiles expect coded diagnoses,
   procedures and medicines rather than free text).

## 3. Phase 1 — Production hardening (code, can start now)

Goal: the app is safe to run on a real server, even before connecting to ABDM.

| # | Work | Where |
|---|---|---|
| 1.1 | Move from SQLite to **PostgreSQL**; add **Alembic** migrations and replace `create_all` plus the hand-written `app/migrations.py` | `database.py`, `main.py`, new `alembic/` |
| 1.2 | Refuse to start without a strong `JWT_SECRET` and an explicit `CORS_ORIGINS`; no insecure defaults | `config.py` |
| 1.3 | **httpOnly, Secure, SameSite cookies** with short-lived access tokens and refresh tokens, instead of `sessionStorage` | `security.py`, `routes/auth.py`, `frontend/src/api.js` |
| 1.4 | Password policy, **login rate limiting and account lockout**, optional **MFA (TOTP)** for staff | `routes/auth.py`, `security.py` |
| 1.5 | Never create sample accounts on production servers (the login page already hides them in production builds); create the first admin with a one-time setup command | `seed.py`, `Login.jsx` |
| 1.6 | **Tamper-evident audit log**: insert-only database permissions plus a hash chain (each row stores the hash of the previous one); export for retention | `models.AuditEvent`, `services.audit` |
| 1.7 | HTTPS everywhere, security headers (HSTS, CSP, X-Frame-Options), request size limits | reverse proxy (e.g. Nginx/Caddy) + FastAPI middleware |
| 1.8 | Encryption at rest (managed PostgreSQL or disk encryption), **daily encrypted backups** with a tested restore | hosting |
| 1.9 | Structured logging without personal data, error monitoring, uptime alerts | `main.py`, hosting |
| 1.10 | **Independent security test** (VAPT) and dependency scanning in CI | CI pipeline |

Exit criteria: security test passed with no high findings; restore from backup rehearsed; no sample
credentials anywhere in the production build.

## 4. Phase 2 — Real identities and coded clinical data

| # | Work | Notes |
|---|---|---|
| 2.1 | Patient model: ABHA number and ABHA address, full name parts, address, verified mobile; keep the internal ID as the primary key | `models.Patient`, registration form |
| 2.2 | Facility model: HFR ID; staff model: HPR ID, professional role | `models.Facility`, `models.User`, admin screens |
| 2.3 | Patient portal accounts: replace "lab sets a temporary password" with self-service sign-up and verified mobile/ABHA login, or rely on the ABHA app for consent (see phase 5) | `routes/patients.py` |
| 2.4 | Coded diagnoses, complaints and procedures (SNOMED CT) and coded medicines, alongside the free text the doctor types | `models.Consultation`, `ConsultationForm.jsx` |
| 2.5 | Rebuild FHIR output against the **ABDM FHIR Implementation Guide** published by NRCeS (current release 6.5.0): `DiagnosticReportRecord` for lab reports, `OPConsultRecord` for consultations, with the required profiles and value sets | `app/fhir.py` |
| 2.6 | Validate with the official IG profiles (e.g. HAPI FHIR validator with the NRCeS package), not only base R4 | `app/fhir.py`, tests |
| 2.7 | Data retention and deletion rules per record type; patient data export | new service |

## 5. Phase 3 — ABDM M1: ABHA (identity)

Build against the sandbox:

- Gateway session (client ID/secret → access token, refreshed automatically).
- **ABHA creation** (Aadhaar or mobile OTP flows) and **ABHA verification/login** for existing ABHA holders.
- Scan-and-share / ABHA-based patient registration at the facility counter.
- Store ABHA details on the patient record; never store Aadhaar numbers.

## 6. Phase 4 — ABDM M2: acting as HIP (sharing your records)

This is the HIP side of what the app simulates today, done through ABDM:

- **Care contexts**: each lab report and consultation becomes a care context linked to the patient's ABHA.
- **Discovery and linking callbacks**: ABDM asks "does this facility have records for this patient?";
  the app answers and links care contexts (with OTP confirmation where required).
- **Health information requests**: when a consent is granted to another facility, ABDM sends the request;
  the app builds the FHIR bundle(s), **encrypts them with ABDM's Fidelius scheme** (ECDH key agreement
  on Curve25519, HKDF-SHA256, AES-256-GCM) and pushes them to the requester's data-push URL, then
  notifies ABDM.
- Our **Shared records** page becomes a view of these real requests and pushes.

Note: guides put care-context linking under M1 or M2 differently. Follow the official sandbox
test-case sheets for exact milestone boundaries.

## 7. Phase 5 — ABDM M3: acting as HIU (requesting records)

- Doctors raise a **consent request through the ABDM consent manager** (purpose, date range, record
  types, expiry), instead of our internal request.
- The patient approves in their **ABHA/PHR app**. Our local Consent Center is retired for cross-facility
  exchange (it can remain for internal workflows only).
- On consent notification, the app requests data, receives encrypted bundles at its data-push endpoint,
  **decrypts** them with its own key pair, validates and displays them, and respects consent expiry
  (deleting fetched data when consent ends, as required).
- Our **Access requests** page becomes a view of real ABDM consent requests and their artefacts.

Optional later: **M4**, digital insurance claims through the National Health Claims Exchange (NHCX).

## 8. Phase 6 — Certification and go-live

1. Pass all sandbox test cases for M1, M2 and M3 (published on the sandbox site as test-case sheets).
2. Complete ABDM's functional review / certification for the software. Certification attaches to the
   software, so it must be repeated for major changes.
3. Receive **production credentials**, switch configuration, and run a pilot at one facility.
4. Vendor guides estimate roughly 4–6 months from sandbox to production when adding ABDM to an existing
   system. Treat that as a rough planning figure, not a commitment.

## 9. Compliance and operations (runs alongside all phases)

- **DPDP Act 2023 / DPDP Rules 2025** (notified 13 November 2025, phased commencement):
  - privacy notice and purpose-specific consent for the app's own processing
  - a grievance contact and a process for access and correction requests
  - reasonable security safeguards (phases 1 and 2)
  - **breach notification**: notify the Data Protection Board and affected people without delay, with a
    detailed report to the Board within 72 hours. These provisions are scheduled to come into force in
    May 2027. Prepare the process now.
- **ABDM policies**: follow ABDM's health data management and security requirements, including where
  data is hosted. Confirm the current requirements with ABDM and counsel.
- **Operations**: incident response runbook, access reviews for staff accounts, audit-log retention, and
  a named on-call contact for ABDM integration issues.

This section is a planning summary, not legal advice.

## 10. What changes in this codebase, at a glance

| Today | After |
|---|---|
| Local `PAT-…` / `FAC-…` IDs and sample users | ABHA, HFR and HPR identifiers |
| Internal Consent Center decides cross-facility access | ABDM consent manager decides; local screens show ABDM state |
| `POST /access-requests/{id}/retrieve` returns data directly | Encrypted push from HIP to HIU through ABDM |
| Base-R4 FHIR validation | NRCeS ABDM IG profile validation |
| SQLite, `create_all`, `app/migrations.py` | PostgreSQL with Alembic |
| `sessionStorage` JWT | httpOnly cookies, refresh tokens, MFA |
| Editable audit table | Tamper-evident, retained audit log |

## 11. Suggested order of work

1. You: start legal advice, HFR/HPR registration and sandbox registration (they take time).
2. Code: phase 1 (hardening), then phase 2 (identities, coded data, NRCeS FHIR).
3. Code + sandbox credentials: phases 3–5 (M1 → M2 → M3).
4. Certification and a pilot at one facility.
5. Only then remove the "Test environment" notice.

## Sources

Most ABDM details below come from integrator guides rather than NHA's own documents. The ABDM
sandbox site and its official test-case sheets are the authority for certification requirements.

- ABDM developer forum — mandatory features for M1/M2 certification: https://devforum.abdm.gov.in/t/mandatory-features-for-m1-m2-certification/6616
- ABDM FHIR Implementation Guide (NRCeS), OPConsultRecord profile: https://nrces.in/ndhm/fhir/r4/StructureDefinition-OPConsultRecord.html
- Integration milestones M1–M4 (vendor guide): https://nirmitee.io/blog/abdm-integration-milestones-m1-m2-m3-m4-multi-software-guide
- Sandbox-to-production certification (vendor guide): https://nirmitee.io/blog/abdm-certification-process-sandbox-to-production-guide/
- HIU (M3) reference architecture (vendor guide): https://nirmitee.io/blog/building-abdm-hiu-from-scratch-m3-flow-reference-architecture/
- Fidelius encryption implementation (vendor guide): https://nirmitee.io/blog/abdm-fidelius-encryption-nodejs-implementation-guide
- fidelius-cli (reference implementation): https://github.com/mgrmtech/fidelius-cli
- DPDP Rules 2025 key highlights: https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/
- DPDP breach notification timeline: https://ksandk.com/md/data-protection-and-data-privacy/dpdp-data-breach-notification-timeline/
- DPDP Act and Rules in healthcare (KPMG): https://assets.kpmg.com/content/dam/kpmgsites/in/pdf/2025/12/the-privacy-prescription-impact-of-dpdp-act-and-rules-in-healthcare-and-life-sciences-sector.pdf.coredownload.pdf
