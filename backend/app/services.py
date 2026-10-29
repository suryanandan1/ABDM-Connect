"""Shared business rules: audit logging, who may view a report, and the consent checks."""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .database import utcnow
from .models import AccessRequest, AuditEvent, Consent, Consultation, Report, User

# Which status changes a person may make. EXPIRED is only set by the system (see refresh_expiry).
ALLOWED_TRANSITIONS = {
    ("PENDING", "ACTIVE"),
    ("PENDING", "DENIED"),
    ("ACTIVE", "REVOKED"),
}


def audit(db: Session, event_type, outcome, user: User | None = None, patient_id=None,
          resource_type=None, resource_id=None, detail=None, username=None):
    """Add one audit row and commit. Never pass passwords, tokens or result values here."""
    db.add(AuditEvent(
        event_type=event_type, outcome=outcome,
        actor_user_id=user.id if user else None,
        actor_username=user.username if user else username,
        actor_role=user.role if user else None,
        patient_id=patient_id, resource_type=resource_type, resource_id=resource_id, detail=detail,
    ))
    db.commit()


def refresh_expiry(db: Session, consent: Consent):
    """Mark an ACTIVE consent as EXPIRED once its end time has passed."""
    if consent.status == "ACTIVE" and consent.expires_at and consent.expires_at <= utcnow():
        consent.status = "EXPIRED"
        db.commit()
        audit(db, "CONSENT_EXPIRED", "SUCCESS", patient_id=consent.patient_id,
              resource_type="Consent", resource_id=consent.id)
    return consent


def change_consent(db: Session, consent: Consent, new_status: str, user: User):
    """Approve, deny or revoke. Only the patient who owns the consent may decide."""
    refresh_expiry(db, consent)
    event = {"ACTIVE": "CONSENT_APPROVED", "DENIED": "CONSENT_DENIED", "REVOKED": "CONSENT_REVOKED"}[new_status]
    if user.role != "PATIENT" or consent.patient_id != user.patient_id:
        audit(db, event, "DENIED", user, consent.patient_id, "Consent", consent.id, "not the consent owner")
        raise HTTPException(404, "Consent not found")
    if (consent.status, new_status) not in ALLOWED_TRANSITIONS:
        audit(db, event, "DENIED", user, consent.patient_id, "Consent", consent.id,
              f"invalid transition {consent.status} -> {new_status}")
        raise HTTPException(409, f"Cannot change a {consent.status} consent to {new_status}")
    now = utcnow()
    consent.status = new_status
    if new_status == "ACTIVE":
        consent.decided_at = now
        consent.expires_at = now + timedelta(days=consent.duration_days)
    elif new_status == "DENIED":
        consent.decided_at = now
    else:
        consent.revoked_at = now
    db.commit()
    audit(db, event, "SUCCESS", user, consent.patient_id, "Consent", consent.id)
    return consent


def consent_problem(db: Session, user: User, req: AccessRequest, purpose: str):
    """Return why a hospital may NOT read the requested record, or None when access is allowed.

    Every value is checked against the logged-in user and the database, never the browser.
    """
    consent = refresh_expiry(db, req.consent)
    record = req.record
    if user.role != "HOSPITAL":
        return "only hospital users can retrieve records through consent"
    if req.requester_facility_id != user.facility_id or consent.requester_facility_id != user.facility_id:
        return "this request belongs to another facility"
    if (consent.report_id != req.report_id or consent.consultation_id != req.consultation_id
            or consent.patient_id != record.patient_id):
        return "consent does not cover this record"
    if consent.status != "ACTIVE":
        return f"consent is {consent.status}"
    if consent.expires_at is None or consent.expires_at <= utcnow():
        return "consent has expired"
    if purpose != consent.purpose:
        return "purpose does not match the approved purpose"
    if record.status == "entered-in-error":
        return "report was withdrawn by the laboratory" if req.report_id else "consultation was withdrawn by the hospital"
    return None


def get_visible_report(db: Session, report_id: int, user: User) -> Report:
    """Direct report access for the lab that created it and the patient it belongs to.

    Hospitals must use the consent-checked retrieve endpoint; admins see no clinical data.
    """
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    allowed = (
        (user.role == "LAB" and report.facility_id == user.facility_id)
        or (user.role == "PATIENT" and report.patient_id == user.patient_id)
    )
    if not allowed:
        audit(db, "REPORT_VIEW", "DENIED", user, report.patient_id, "Report", report.id, "no direct access")
        if user.role == "HOSPITAL":
            raise HTTPException(403, "Hospitals can read reports only through an approved access request")
        raise HTTPException(403, "You do not have access to this report")
    return report


def get_visible_consultation(db: Session, consultation_id: int, user: User) -> Consultation:
    """A consultation is visible to the hospital that wrote it and to the patient it belongs to.

    Other hospitals, labs and admins get 403 (admins see no clinical data).
    """
    consultation = db.get(Consultation, consultation_id)
    if consultation is None:
        raise HTTPException(404, "Consultation not found")
    allowed = (
        (user.role == "HOSPITAL" and consultation.facility_id == user.facility_id)
        or (user.role == "PATIENT" and consultation.patient_id == user.patient_id)
    )
    if not allowed:
        audit(db, "CONSULTATION_VIEW", "DENIED", user, consultation.patient_id, "Consultation", consultation.id,
              "not the authoring facility or the patient")
        raise HTTPException(403, "You do not have access to this consultation")
    return consultation
