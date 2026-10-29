from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import fhir, loinc
from ..database import get_db
from ..models import Observation, User
from ..security import get_current_user, require_roles
from ..services import get_visible_report
from .patients import get_patient_for

router = APIRouter(tags=["fhir"])


def fhir_json(resource):
    return JSONResponse(resource, media_type="application/fhir+json")


@router.get("/fhir/metadata")
def metadata():
    return fhir_json(fhir.capability_statement())


@router.get("/fhir/Patient/{patient_id}")
def fhir_patient(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return fhir_json(fhir.patient_resource(get_patient_for(db, patient_id, user)))


@router.get("/fhir/DiagnosticReport/{report_id}")
def fhir_diagnostic_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return fhir_json(fhir.diagnostic_report_resource(get_visible_report(db, report_id, user)))


@router.get("/fhir/Observation/{observation_id}")
def fhir_observation(observation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obs = db.get(Observation, observation_id)
    if obs is None:
        raise HTTPException(404, "Observation not found")
    report = get_visible_report(db, obs.report_id, user)
    return fhir_json(fhir.observation_resource(obs, report))


@router.get("/loinc/search")
def loinc_search(q: str, kind: str | None = None, _: User = Depends(require_roles("LAB", "ADMIN"))):
    if kind not in (None, "test", "panel"):
        raise HTTPException(422, "kind must be 'test' or 'panel'")
    return loinc.search(q, kind)


@router.get("/loinc/units")
def loinc_units(_: User = Depends(get_current_user)):
    """UCUM unit codes accepted for results (used by the report form)."""
    return sorted(loinc.ALLOWED_UNITS)
