"""Doctor consultations: a hospital doctor records a visit; the patient can read it."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fhir
from ..database import get_db
from ..models import Consultation, Medication, Patient, User
from ..schemas import ConsultationBrief, ConsultationIn, ConsultationOut, ConsultationSummary
from ..security import get_current_user, require_roles
from ..services import audit, get_visible_consultation

router = APIRouter(tags=["consultations"])


def clean(text):
    text = (text or "").strip()
    return text or None


@router.post("/consultations", response_model=ConsultationOut, status_code=201)
def create_consultation(data: ConsultationIn, user: User = Depends(require_roles("HOSPITAL")),
                        db: Session = Depends(get_db)):
    if db.get(Patient, data.patient_id) is None:
        raise HTTPException(404, "Patient not found")
    consultation = Consultation(
        patient_id=data.patient_id, facility_id=user.facility_id, doctor_user_id=user.id,
        visit_at=data.visit_at, chief_complaint=data.chief_complaint.strip(), examination=clean(data.examination),
        diagnosis=data.diagnosis.strip(), advice=clean(data.advice), follow_up_date=data.follow_up_date,
        bp_systolic=data.bp_systolic, bp_diastolic=data.bp_diastolic, pulse=data.pulse,
        temperature=data.temperature, spo2=data.spo2, weight=data.weight,
        medications=[
            Medication(name=m.name.strip(), dosage=m.dosage.strip(), frequency=m.frequency.strip(),
                       duration=m.duration.strip(), instructions=clean(m.instructions))
            for m in data.medications
        ],
    )
    db.add(consultation)
    db.commit()
    audit(db, "CONSULTATION_CREATED", "SUCCESS", user, consultation.patient_id, "Consultation", consultation.id,
          f"{len(consultation.medications)} medication(s)")
    return consultation


@router.get("/consultations", response_model=list[ConsultationSummary])
def list_consultations(user: User = Depends(require_roles("HOSPITAL", "PATIENT")), db: Session = Depends(get_db)):
    """HOSPITAL: consultations written at its facility. PATIENT: their own consultations."""
    query = select(Consultation).order_by(Consultation.visit_at.desc()).limit(200)
    if user.role == "HOSPITAL":
        query = query.where(Consultation.facility_id == user.facility_id)
    else:
        query = query.where(Consultation.patient_id == user.patient_id)
    return db.scalars(query).all()


@router.get("/patients/{patient_id}/consultations", response_model=list[ConsultationSummary])
def patient_consultations(patient_id: int, user: User = Depends(require_roles("HOSPITAL")),
                          db: Session = Depends(get_db)):
    """A hospital sees only the consultations its own doctors wrote for this patient."""
    if db.get(Patient, patient_id) is None:
        raise HTTPException(404, "Patient not found")
    query = (select(Consultation)
             .where(Consultation.patient_id == patient_id, Consultation.facility_id == user.facility_id)
             .order_by(Consultation.visit_at.desc()))
    return db.scalars(query).all()


@router.get("/patients/{patient_id}/consultations/other-facilities", response_model=list[ConsultationBrief])
def other_facility_consultations(patient_id: int, user: User = Depends(require_roles("HOSPITAL")),
                                 db: Session = Depends(get_db)):
    """Consultations this patient had at OTHER hospitals: date, hospital and doctor only.

    The clinical content is available only through a consent-checked access request.
    """
    if db.get(Patient, patient_id) is None:
        raise HTTPException(404, "Patient not found")
    query = (select(Consultation)
             .where(Consultation.patient_id == patient_id, Consultation.facility_id != user.facility_id,
                    Consultation.status != "entered-in-error")
             .order_by(Consultation.visit_at.desc()))
    return db.scalars(query).all()


@router.get("/consultations/{consultation_id}", response_model=ConsultationOut)
def get_consultation(consultation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_visible_consultation(db, consultation_id, user)


@router.get("/consultations/{consultation_id}/fhir")
def get_consultation_fhir(consultation_id: int, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """The consultation as a FHIR document Bundle, plus base-R4 validation results."""
    return fhir.with_validation(fhir.consultation_bundle(get_visible_consultation(db, consultation_id, user)))


@router.post("/consultations/{consultation_id}/withdraw", response_model=ConsultationOut)
def withdraw_consultation(consultation_id: int, user: User = Depends(require_roles("HOSPITAL")),
                          db: Session = Depends(get_db)):
    """Mark a consultation as entered in error. It stays stored, visibly marked, for the record."""
    consultation = get_visible_consultation(db, consultation_id, user)
    if consultation.status == "entered-in-error":
        raise HTTPException(409, "Consultation is already withdrawn")
    consultation.status = "entered-in-error"
    db.commit()
    audit(db, "CONSULTATION_WITHDRAWN", "SUCCESS", user, consultation.patient_id, "Consultation", consultation.id)
    return consultation
