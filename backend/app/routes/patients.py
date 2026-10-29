import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Facility, Patient, Report, User
from ..schemas import FacilityOut, PatientIn, PatientOut, ReportSummary
from ..security import get_current_user, hash_password, require_roles
from ..services import audit

router = APIRouter(tags=["patients"])


def get_patient_for(db: Session, patient_id: int, user: User) -> Patient:
    patient = db.get(Patient, patient_id)
    # A patient may only see their own record; 404 avoids revealing that other records exist.
    if patient is None or (user.role == "PATIENT" and user.patient_id != patient_id):
        raise HTTPException(404, "Patient not found")
    return patient


@router.post("/patients", response_model=PatientOut, status_code=201)
def register_patient(data: PatientIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    duplicate = db.scalar(select(Patient).where(
        func.lower(Patient.full_name) == data.full_name.strip().lower(), Patient.birth_date == data.birth_date))
    if duplicate:
        raise HTTPException(409, f"A patient with this name and birth date already exists ({duplicate.patient_code})")
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "That username is already taken")
    patient = Patient(
        patient_code="TMP-" + secrets.token_hex(6), full_name=data.full_name.strip(), gender=data.gender,
        birth_date=data.birth_date, phone=data.phone, registered_by_facility_id=user.facility_id,
    )
    db.add(patient)
    db.flush()  # gives the patient its id
    patient.patient_code = f"PAT-{patient.id:06d}"
    db.add(User(username=data.username, password_hash=hash_password(data.password),
                full_name=patient.full_name, role="PATIENT", patient_id=patient.id))
    db.commit()
    audit(db, "PATIENT_CREATED", "SUCCESS", user, patient.id, "Patient", patient.id)
    return patient


@router.get("/patients", response_model=list[PatientOut])
def list_patients(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Patient).order_by(Patient.full_name).limit(50)
    if user.role == "PATIENT":
        query = query.where(Patient.id == user.patient_id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Patient.full_name.ilike(like), Patient.patient_code.ilike(like), Patient.phone.ilike(like)))
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
