# ABDM Connect API (v1)

Base URL: `http://localhost:8000/api/v1`. Interactive docs: `http://localhost:8000/docs`.

These are this application's own endpoints. **They are not official ABDM API paths.**

All endpoints except `POST /auth/login`, `GET /fhir/metadata` and `GET /health` need
`Authorization: Bearer <token>`. Roles: `ADMIN`, `LAB` (HIP), `HOSPITAL` (HIP + HIU), `PATIENT`.

Errors always look like `{"detail": "..."}` or, for validation errors (422), `{"detail": [...]}`.

| Code | Meaning |
|------|---------|
| 401 | Missing, invalid, expired or logged-out token / wrong login |
| 403 | Logged in, but this role or this user may not do it (consent checks also return 403) |
| 404 | Not found, or belongs to someone you may not see |
| 409 | Duplicate, or an invalid consent state change |
| 422 | Request body failed validation |

## Authentication

| Method & path | Who | Notes |
|---|---|---|
| `POST /auth/login` | anyone | Body `{username, password}`. Returns `{access_token, token_type, expires_in, user}`. Audited (success and failure). |
| `GET /auth/me` | any role | The logged-in user, with facility. |
| `POST /auth/logout` | any role | 204. Invalidates **all** tokens of this user (token version is bumped). |

## Patients and facilities

| Method & path | Who | Notes |
|---|---|---|
| `POST /patients` | LAB | Body `{full_name, gender, birth_date, phone?, username, password}`. Creates the patient (patient ID `PAT-nnnnnn`, not an ABHA number) and their portal login. 409 if same name + birth date or username exists. |
| `GET /patients?q=` | any role | Search name / patient ID / phone (max 50). A patient only gets their own record. |
| `GET /patients/{id}` | any role | Patient: only self (else 404). |
| `GET /patients/{id}/reports` | any role | Report list **without results**. LAB: only its own facility's reports. HOSPITAL: withdrawn reports hidden. |
| `GET /facilities` | any role | All facilities (each with a `facility_code` such as `FAC-LAB-001`). |
| `POST /facilities` | ADMIN | Body `{name, facility_type: LAB|HOSPITAL, city}`. |

## Laboratory reports

| Method & path | Who | Notes |
|---|---|---|
| `POST /reports` | LAB | Body below. Facility is always the lab user's own facility. |
| `GET /reports` | LAB, PATIENT | LAB: facility's reports. PATIENT: own reports. |
| `GET /reports/{id}` | LAB (same facility), PATIENT (owner) | Full report with observations. HOSPITAL/ADMIN get 403 (hospitals must use retrieve). |
| `GET /reports/{id}/fhir` | same as above | `{resource: <FHIR document Bundle>, validation: {valid, errors, checked_against}}` |
| `POST /reports/{id}/withdraw` | LAB (same facility) | Sets status `entered-in-error`; it can then no longer be requested or retrieved. |

`POST /reports` body:

```json
{
  "patient_id": 1,
  "title": "Complete Blood Count",
  "panel_loinc_code": "58410-2",
  "collected_at": "2026-10-29T05:30:00Z",
  "conclusion": "optional text",
  "observations": [
    {"test_name": "Hemoglobin", "loinc_code": "718-7", "value": 13.2, "unit": "g/dL", "ref_low": 12, "ref_high": 15.5}
  ]
}
```

Rules: 1–30 observations; each `loinc_code` must exist in the local LOINC table as a test (panel code as a
panel); no code twice in one report; `unit` must be a supported UCUM code (`GET /loinc/units`); value ≥ 0;
`ref_low ≤ ref_high`; `collected_at` has a time zone and is not in the future. The stored LOINC display
always comes from the LOINC table, and the interpretation (L/N/H) is calculated by the server.

## Doctor consultations (OP consultation record)

A hospital doctor records an outpatient visit; the patient can read it in their portal.
Visible only to the **authoring hospital** and the **patient** (other hospitals, labs and admins get 403, audited as `CONSULTATION_VIEW` DENIED).

| Method & path | Who | Notes |
|---|---|---|
| `POST /consultations` | HOSPITAL | Body `{patient_id, visit_at, chief_complaint, examination?, diagnosis, advice?, follow_up_date?, bp_systolic?, bp_diastolic?, pulse?, temperature?, spo2?, weight?, medications: [{name, dosage, frequency, duration, instructions?}]}`. `visit_at` must have a time zone and not be in the future; BP needs both values with systolic > diastolic; follow-up not before the visit; max 20 medicines. Audited `CONSULTATION_CREATED`. |
| `GET /consultations` | HOSPITAL, PATIENT | HOSPITAL: its facility's consultations. PATIENT: their own. Newest visit first (max 200). |
| `GET /patients/{id}/consultations` | HOSPITAL | This patient's consultations written at the caller's hospital. |
| `GET /consultations/{id}` | authoring HOSPITAL, PATIENT | Full consultation with vitals and medications. |
| `GET /consultations/{id}/fhir` | authoring HOSPITAL, PATIENT | FHIR R4 document Bundle: Composition (LOINC 11488-4 *Consult note*), Patient, Organization, Practitioner, Encounter (AMB), Condition (chief complaint, diagnosis), Observation (examination, vital signs), MedicationRequest, Appointment (follow-up), plus base-R4 validation. Complaints, diagnoses and medicines are free text (SNOMED CT / drug terminology is planned, see PRODUCTION_PLAN.md). |
| `POST /consultations/{id}/withdraw` | authoring HOSPITAL | Marks it `entered-in-error`; the patient still sees it, clearly marked. 409 if already withdrawn. Audited `CONSULTATION_WITHDRAWN`. |

## Access requests (simulated HIP / HIU flow)

Facilities play two roles. A **LAB** is an HIP (it holds lab reports). A **HOSPITAL** is both: an HIU when it
requests a record, and an HIP when another hospital requests one of its consultations. The patient always
decides; the holding facility (HIP) never approves.

| Method & path | Who | Notes |
|---|---|---|
| `POST /access-requests` | HOSPITAL | Body `{report_id` **or** `consultation_id, purpose, duration_days (1-30, default 7)}` (exactly one record, else 422). Purpose: `TREAT`, `ETREAT`, `PUBHLTH`, `HRESCH` (HL7 v3 PurposeOfUse codes). Creates a PENDING consent; the patient is taken from the record. 409 if this facility already has a PENDING/ACTIVE request for the record, or if it requests its own consultation. 404 for unknown or withdrawn records. |
| `GET /access-requests` | HOSPITAL (requests it made, HIU), PATIENT (own), ADMIN (all) | Each item includes its consent and either `report` or `consultation` (the other is `null`). Consultations are shown as metadata only (`visit_at`, facility, doctor). `status` is the consent's status. |
| `GET /access-requests/incoming` | LAB, HOSPITAL | **HIP view**: requests from other facilities for records held by the caller's facility. Read-only, no clinical data. |
| `GET /access-requests/{id}` | same scope as the list | 404 outside your scope. |
| `POST /access-requests/{id}/retrieve` | HOSPITAL | Body `{purpose}`. Returns `{report, fhir, consent_expires_at}` or `{consultation, fhir, consent_expires_at}` only if every consent check passes; otherwise 403 `Access denied: <reason>`. Audited as `REPORT_RETRIEVE` / `CONSULTATION_RETRIEVE`. |
| `GET /patients/{id}/consultations/other-facilities` | HOSPITAL | The patient's consultations at other hospitals, metadata only, for choosing what to request. |

Checks done on every retrieve (in `services.consent_problem`): caller is a hospital user; request and
consent belong to the caller's facility; consent covers exactly this record and its patient; status is
ACTIVE; not past `expires_at`; purpose matches; record not withdrawn.

**Upgrading an older database:** at startup (and in `python -m app.seed`) `app/migrations.py` rebuilds the
`consents` and `access_requests` tables to add `consultation_id` and make `report_id` optional. Rows are
copied unchanged and the database file is first copied to `abdm_connect.db.bak-hip-hiu`.

## Consent (simulated, not the ABDM Consent Manager)

| Method & path | Who | Notes |
|---|---|---|
| `GET /consents` | PATIENT (own), ADMIN | |
| `GET /consents/{id}` | PATIENT (own), ADMIN | |
| `POST /consents/{id}/approve` | PATIENT (owner) | PENDING → ACTIVE. Sets `expires_at = now + duration_days`. |
| `POST /consents/{id}/deny` | PATIENT (owner) | PENDING → DENIED. |
| `POST /consents/{id}/revoke` | PATIENT (owner) | ACTIVE → REVOKED. |

Any other transition returns 409. ACTIVE consents become EXPIRED automatically when they are next read
after `expires_at`.

## FHIR R4 and LOINC

| Method & path | Who | Notes |
|---|---|---|
| `GET /fhir/metadata` | public | CapabilityStatement (`fhirVersion` 4.0.1). |
| `GET /fhir/Patient/{id}` | any role (patients: self) | `application/fhir+json` |
| `GET /fhir/DiagnosticReport/{id}` | LAB (same facility), PATIENT (owner) | |
| `GET /fhir/Observation/{id}` | LAB (same facility), PATIENT (owner) | |
| `GET /loinc/search?q=&kind=test|panel` | LAB, ADMIN | Ranked: exact code/abbreviation, then prefix, then contains. Max 20. |
| `GET /loinc/units` | any role | Supported UCUM unit codes. |

## Admin and audit

| Method & path | Who | Notes |
|---|---|---|
| `GET /admin/stats` | ADMIN | Counts of users, facilities, patients, reports, requests, consents by status, denied events. |
| `GET /admin/users` | ADMIN | |
| `POST /admin/users` | ADMIN | Body `{username, password, full_name, role: ADMIN|LAB|HOSPITAL, facility_id}`. LAB/HOSPITAL need a facility of the same type. |
| `PATCH /admin/users/{id}` | ADMIN | Body any of `{full_name, is_active, password}`. A password reset signs the user out everywhere. You cannot deactivate yourself. |
| `GET /audit-events?event_type=&outcome=&patient_id=&limit=` | ADMIN (all), PATIENT (events about themselves) | Newest first, default 200, max 1000. |

Audit event types: `LOGIN`, `LOGOUT`, `PATIENT_CREATED`, `REPORT_CREATED`, `REPORT_WITHDRAWN`, `REPORT_VIEW`
(denied direct reads), `ACCESS_REQUESTED`, `CONSENT_APPROVED`, `CONSENT_DENIED`, `CONSENT_REVOKED`,
`CONSENT_EXPIRED`, `REPORT_RETRIEVE`, `ADMIN_USER_CREATED`, `ADMIN_USER_UPDATED`, `ADMIN_FACILITY_CREATED`.
Outcomes: `SUCCESS`, `DENIED`, `FAILURE`. Audit rows never contain passwords, tokens or result values.
