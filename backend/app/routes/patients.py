import secrets
from datetime import date, timedelta
from typing import NoReturn

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import abdm
from ..config import JWT_SECRET
from ..database import get_db, utcnow
from ..models import Facility, Patient, Report, User
from ..schemas import (
    AbhaInitIn, AbhaInitOut, AbhaLinkIn, AbhaProfile, AbhaRegisterIn, AbhaVerifyIn, AbhaVerifyOut,
    FacilityOut, PatientIn, PatientOut, ReportSummary,
)
from ..security import get_current_user, hash_password, require_roles
from ..services import audit

router = APIRouter(tags=["patients"])


def get_patient_for(db: Session, patient_id: int, user: User) -> Patient:
    patient = db.get(Patient, patient_id)
    # A patient may only see their own record; 404 avoids revealing that other records exist.
    if patient is None or (user.role == "PATIENT" and user.patient_id != patient_id):
        raise HTTPException(404, "Patient not found")
    return patient


def find_duplicate(db: Session, full_name: str, birth_date: date) -> Patient | None:
    return db.scalar(select(Patient).where(
        func.lower(Patient.full_name) == full_name.strip().lower(), Patient.birth_date == birth_date))


def create_patient(db: Session, user: User, username: str, password: str, **fields) -> Patient:
    """Create the patient and their portal login. Caller has already checked for duplicates."""
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "That username is already taken")
    patient = Patient(patient_code="TMP-" + secrets.token_hex(6), registered_by_facility_id=user.facility_id, **fields)
    db.add(patient)
    db.flush()  # gives the patient its id
    patient.patient_code = f"PAT-{patient.id:06d}"
    db.add(User(username=username, password_hash=hash_password(password),
                full_name=patient.full_name, role="PATIENT", patient_id=patient.id))
    db.commit()
    return patient


@router.post("/patients", response_model=PatientOut, status_code=201)
def register_patient(data: PatientIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    duplicate = find_duplicate(db, data.full_name, data.birth_date)
    if duplicate:
        raise HTTPException(409, f"A patient with this name and birth date already exists ({duplicate.patient_code})")
    patient = create_patient(db, user, data.username, data.password, full_name=data.full_name.strip(),
                             gender=data.gender, birth_date=data.birth_date, phone=data.phone)
    audit(db, "PATIENT_CREATED", "SUCCESS", user, patient.id, "Patient", patient.id)
    return patient


# ---------- Registration with ABHA (verified through ABDM; today the local mock server) ----------
# 1. /abha/init sends an OTP to the patient's ABHA-linked mobile.
# 2. /abha/verify checks the OTP and returns the verified profile, signed as `abha_token`.
# 3. /abha/register creates a new patient from that profile, or /patients/{id}/abha links it to an existing one.
ABHA_TOKEN_MINUTES = 15


def mask_abha(abha_number: str) -> str:
    return "ABHA ****-" + abha_number[-4:]


def abdm_failed(db: Session, user: User, event: str, err: abdm.AbdmError) -> NoReturn:
    audit(db, event, "FAILURE", user, detail=err.message[:255])
    raise HTTPException(err.status, err.message)


def read_abha_token(token: str, user: User) -> AbhaProfile:
    """The signed profile from /abha/verify; only the staff member who verified it may use it."""
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "ABHA verification expired. Verify the OTP again.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid ABHA verification") from None
    if claims.get("typ") != "abha-profile" or claims.get("by") != user.id:
        raise HTTPException(400, "Invalid ABHA verification")
    return AbhaProfile(**claims["profile"])


def abha_owner(db: Session, profile: AbhaProfile) -> Patient | None:
    conditions = [Patient.abha_number == profile.abha_number]
    if profile.abha_address:
        conditions.append(Patient.abha_address == profile.abha_address)
    return db.scalar(select(Patient).where(or_(*conditions)))


@router.post("/patients/abha/init", response_model=AbhaInitOut)
def abha_init(data: AbhaInitIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    try:
        result = abdm.request_otp(abha_number=data.abha_number and data.abha_number.strip(),
                                  abha_address=data.abha_address and data.abha_address.strip().lower())
    except abdm.AbdmError as err:
        abdm_failed(db, user, "ABHA_OTP_REQUESTED", err)
    audit(db, "ABHA_OTP_REQUESTED", "SUCCESS", user)
    return AbhaInitOut(txn_id=result["txnId"], message=result.get("message", "OTP sent"))


@router.post("/patients/abha/verify", response_model=AbhaVerifyOut)
def abha_verify(data: AbhaVerifyIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    try:
        profile = AbhaProfile(**abdm.verify_otp_and_get_profile(data.txn_id, data.otp))
    except abdm.AbdmError as err:
        abdm_failed(db, user, "ABHA_VERIFIED", err)
    existing = abha_owner(db, profile)
    match = None if existing else find_duplicate(db, profile.full_name, profile.birth_date)
    audit(db, "ABHA_VERIFIED", "SUCCESS", user, existing.id if existing else None, detail=mask_abha(profile.abha_number))
    token = jwt.encode({
        "typ": "abha-profile", "by": user.id, "profile": profile.model_dump(mode="json"),
        "exp": utcnow() + timedelta(minutes=ABHA_TOKEN_MINUTES),
    }, JWT_SECRET, algorithm="HS256")
    return AbhaVerifyOut(abha_token=token, profile=profile, existing_patient=existing,
                         possible_match=match if match and not match.abha_number else None)


@router.post("/patients/abha/register", response_model=PatientOut, status_code=201)
def abha_register(data: AbhaRegisterIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    profile = read_abha_token(data.abha_token, user)
    existing = abha_owner(db, profile)
    if existing:
        raise HTTPException(409, f"This ABHA is already registered ({existing.patient_code})")
    duplicate = find_duplicate(db, profile.full_name, profile.birth_date)
    if duplicate:
        raise HTTPException(409, f"A patient with this name and birth date already exists ({duplicate.patient_code}). "
                                 "Link the ABHA to that record instead.")
    patient = create_patient(
        db, user, data.username, data.password, full_name=profile.full_name, gender=profile.gender,
        birth_date=profile.birth_date, phone=profile.phone, abha_number=profile.abha_number,
        abha_address=profile.abha_address, abha_verified_at=utcnow(),
    )
    audit(db, "PATIENT_CREATED", "SUCCESS", user, patient.id, "Patient", patient.id,
          detail="Registered with verified " + mask_abha(profile.abha_number))
    return patient


@router.post("/patients/{patient_id}/abha", response_model=PatientOut)
def abha_link(patient_id: int, data: AbhaLinkIn, user: User = Depends(require_roles("LAB")),
              db: Session = Depends(get_db)):
    """Attach a verified ABHA to a patient who was registered manually before."""
    profile = read_abha_token(data.abha_token, user)
    patient = get_patient_for(db, patient_id, user)
    if patient.abha_number and patient.abha_number != profile.abha_number:
        raise HTTPException(409, "This patient is already linked to a different ABHA")
    existing = abha_owner(db, profile)
    if existing and existing.id != patient.id:
        raise HTTPException(409, f"This ABHA is already registered ({existing.patient_code})")
    # Linking on name + birth date alone could attach someone else's ABHA, so they must match exactly.
    if patient.full_name.strip().lower() != profile.full_name.strip().lower() or patient.birth_date != profile.birth_date:
        raise HTTPException(409, "Name or birth date on the ABHA does not match this patient record")
    patient.abha_number, patient.abha_address, patient.abha_verified_at = (
        profile.abha_number, profile.abha_address, utcnow())
    db.commit()
    audit(db, "ABHA_LINKED", "SUCCESS", user, patient.id, "Patient", patient.id, detail=mask_abha(profile.abha_number))
    return patient


@router.get("/patients", response_model=list[PatientOut])
def list_patients(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Patient).order_by(Patient.full_name).limit(50)
    if user.role == "PATIENT":
        query = query.where(Patient.id == user.patient_id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Patient.full_name.ilike(like), Patient.patient_code.ilike(like), Patient.phone.ilike(like),
                                Patient.abha_number.ilike(like), Patient.abha_address.ilike(like)))
    return db.scalars(query).all()


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_patient_for(db, patient_id, user)


@router.get("/patients/{patient_id}/reports", response_model=list[ReportSummary])
def patient_reports(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Report list without results. Labs see only their own facility's reports."""
    get_patient_for(db, patient_id, user)
    query = select(Report).where(Report.patient_id == patient_id).order_by(Report.issued_at.desc())
    if user.role == "LAB":
        query = query.where(Report.facility_id == user.facility_id)
    if user.role == "HOSPITAL":
        query = query.where(Report.status != "entered-in-error")
    return db.scalars(query).all()


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Facility).order_by(Facility.name)).all()
