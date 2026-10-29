"""Simulated HIU access requests and patient consent (a local simulation, not the ABDM Consent Manager).

A hospital is an HIU when it requests a record and an HIP when another facility requests one of
its consultations. Labs are HIPs only. The patient always decides; the HIP never approves.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import fhir
from ..database import get_db
from ..models import AccessRequest, Consent, Consultation, Report, User
from ..schemas import AccessRequestIn, AccessRequestOut, ConsentOut, ConsultationOut, ReportOut, RetrieveIn
from ..security import get_current_user, require_roles
from ..services import audit, change_consent, consent_problem, refresh_expiry

router = APIRouter(tags=["consent"])


def scoped_requests(user: User):
    """Access requests the user is allowed to see."""
    query = select(AccessRequest).order_by(AccessRequest.created_at.desc())
    if user.role == "HOSPITAL":
        return query.where(AccessRequest.requester_facility_id == user.facility_id)
    if user.role == "PATIENT":
        return query.where(AccessRequest.patient_id == user.patient_id)
    if user.role == "ADMIN":
        return query
    raise HTTPException(403, "Your role is not allowed to do this")


def scoped_consents(user: User):
    query = select(Consent).order_by(Consent.created_at.desc())
    if user.role == "PATIENT":
        return query.where(Consent.patient_id == user.patient_id)
    if user.role == "ADMIN":
        return query
    raise HTTPException(403, "Your role is not allowed to do this")


@router.post("/access-requests", response_model=AccessRequestOut, status_code=201)
def create_access_request(data: AccessRequestIn, user: User = Depends(require_roles("HOSPITAL")),
                          db: Session = Depends(get_db)):
    if data.report_id is not None:
        kind, column, record = "report", AccessRequest.report_id, db.get(Report, data.report_id)
    else:
        kind, column, record = "consultation", AccessRequest.consultation_id, db.get(Consultation, data.consultation_id)
    if record is None or record.status == "entered-in-error":
        raise HTTPException(404, f"{kind.capitalize()} not found")
    if kind == "consultation" and record.facility_id == user.facility_id:
        raise HTTPException(409, "This consultation was written at your hospital; open it directly")
    open_request = db.scalar(select(AccessRequest).join(Consent).where(
        AccessRequest.requester_facility_id == user.facility_id,
        column == record.id,
        Consent.status.in_(["PENDING", "ACTIVE"]),
    ))
    if open_request and refresh_expiry(db, open_request.consent).status in ("PENDING", "ACTIVE"):
        raise HTTPException(409, f"Your facility already has a {open_request.status} request for this {kind}")
    # The patient is taken from the record itself, never from the browser.
    scope = {"report_id": data.report_id} if kind == "report" else {"consultation_id": data.consultation_id}
    consent = Consent(patient_id=record.patient_id, requester_facility_id=user.facility_id,
                      purpose=data.purpose, duration_days=data.duration_days, **scope)
    req = AccessRequest(requester_user_id=user.id, requester_facility_id=user.facility_id,
                        patient_id=record.patient_id, purpose=data.purpose, consent=consent, **scope)
    db.add(req)
    db.commit()
    audit(db, "ACCESS_REQUESTED", "SUCCESS", user, record.patient_id, "AccessRequest", req.id,
          f"{kind} {record.id}, purpose {data.purpose}")
    return req


@router.get("/access-requests", response_model=list[AccessRequestOut])
def list_access_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    requests = db.scalars(scoped_requests(user)).all()
    for r in requests:
        refresh_expiry(db, r.consent)
    return requests


@router.get("/access-requests/incoming", response_model=list[AccessRequestOut])
def incoming_requests(user: User = Depends(require_roles("LAB", "HOSPITAL")), db: Session = Depends(get_db)):
    """HIP view: requests from other facilities for records held by the caller's facility.

    Read-only and without clinical data: only the patient can approve or deny.
    """
    query = (select(AccessRequest)
             .where(or_(AccessRequest.report.has(Report.facility_id == user.facility_id),
                        AccessRequest.consultation.has(Consultation.facility_id == user.facility_id)))
             .order_by(AccessRequest.created_at.desc()).limit(200))
    requests = db.scalars(query).all()
    for r in requests:
        refresh_expiry(db, r.consent)
    return requests


@router.get("/access-requests/{request_id}", response_model=AccessRequestOut)
def get_access_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.scalar(scoped_requests(user).where(AccessRequest.id == request_id))
    if req is None:
        raise HTTPException(404, "Access request not found")
    refresh_expiry(db, req.consent)
    return req


@router.post("/access-requests/{request_id}/retrieve")
def retrieve_report(request_id: int, data: RetrieveIn, user: User = Depends(require_roles("HOSPITAL")),
                    db: Session = Depends(get_db)):
    """The only way a hospital can read another facility's record: every consent rule is checked on each call."""
    req = db.get(AccessRequest, request_id)
    if req is None:
        raise HTTPException(404, "Access request not found")
    if req.consultation_id is not None:
        return retrieve_consultation(db, user, req, data.purpose)
    problem = consent_problem(db, user, req, data.purpose)
    if problem:
        audit(db, "REPORT_RETRIEVE", "DENIED", user, req.patient_id, "Report", req.report_id, problem)
        raise HTTPException(403, f"Access denied: {problem}")
    audit(db, "REPORT_RETRIEVE", "SUCCESS", user, req.patient_id, "Report", req.report_id,
          f"consent {req.consent_id}")
    return {
        "report": ReportOut.model_validate(req.report),
        "fhir": fhir.with_validation(fhir.report_bundle(req.report)),
        "consent_expires_at": req.consent.expires_at,
    }


def retrieve_consultation(db: Session, user: User, req: AccessRequest, purpose: str):
    problem = consent_problem(db, user, req, purpose)
    if problem:
        audit(db, "CONSULTATION_RETRIEVE", "DENIED", user, req.patient_id, "Consultation", req.consultation_id, problem)
        raise HTTPException(403, f"Access denied: {problem}")
    audit(db, "CONSULTATION_RETRIEVE", "SUCCESS", user, req.patient_id, "Consultation", req.consultation_id,
          f"consent {req.consent_id}")
    return {
        "consultation": ConsultationOut.model_validate(req.consultation),
        "fhir": fhir.with_validation(fhir.consultation_bundle(req.consultation)),
        "consent_expires_at": req.consent.expires_at,
    }


@router.get("/consents", response_model=list[ConsentOut])
def list_consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    consents = db.scalars(scoped_consents(user)).all()
    for c in consents:
        refresh_expiry(db, c)
    return consents


@router.get("/consents/{consent_id}", response_model=ConsentOut)
def get_consent(consent_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    consent = db.scalar(scoped_consents(user).where(Consent.id == consent_id))
    if consent is None:
        raise HTTPException(404, "Consent not found")
    return refresh_expiry(db, consent)


def decide(consent_id: int, new_status: str, user: User, db: Session):
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise HTTPException(404, "Consent not found")
    return change_consent(db, consent, new_status, user)


@router.post("/consents/{consent_id}/approve", response_model=ConsentOut)
def approve(consent_id: int, user: User = Depends(require_roles("PATIENT")), db: Session = Depends(get_db)):
    return decide(consent_id, "ACTIVE", user, db)


@router.post("/consents/{consent_id}/deny", response_model=ConsentOut)
def deny(consent_id: int, user: User = Depends(require_roles("PATIENT")), db: Session = Depends(get_db)):
    return decide(consent_id, "DENIED", user, db)


@router.post("/consents/{consent_id}/revoke", response_model=ConsentOut)
def revoke(consent_id: int, user: User = Depends(require_roles("PATIENT")), db: Session = Depends(get_db)):
    return decide(consent_id, "REVOKED", user, db)
