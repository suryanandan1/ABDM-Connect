from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fhir, loinc
from ..database import get_db
from ..models import Observation, Patient, Report, User
from ..schemas import ReportIn, ReportOut, ReportSummary
from ..security import get_current_user, require_roles
from ..services import audit, get_visible_report

router = APIRouter(tags=["reports"])


def interpret(value, low, high):
    if low is not None and value < low:
        return "L"
    if high is not None and value > high:
        return "H"
    return "N" if low is not None or high is not None else None


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(data: ReportIn, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    if db.get(Patient, data.patient_id) is None:
        raise HTTPException(404, "Patient not found")
    errors = []
    if data.panel_loinc_code:
        panel = loinc.get_concept(data.panel_loinc_code)
        if panel is None or panel["kind"] != "panel":
            errors.append(f"Panel code {data.panel_loinc_code} is not a known LOINC panel")
    codes = [o.loinc_code for o in data.observations]
    for i, o in enumerate(data.observations, start=1):
        concept = loinc.get_concept(o.loinc_code)
        if concept is None or concept["kind"] != "test":
            errors.append(f"Row {i}: LOINC code {o.loinc_code} is not a known test code")
        if codes.count(o.loinc_code) > 1:
            errors.append(f"Row {i}: LOINC code {o.loinc_code} is used more than once")
    if errors:
        raise HTTPException(422, sorted(set(errors)))

    report = Report(
        patient_id=data.patient_id, facility_id=user.facility_id, created_by_user_id=user.id,
        title=data.title.strip(), panel_loinc_code=data.panel_loinc_code or None,
        collected_at=data.collected_at, conclusion=data.conclusion,
        observations=[
            Observation(
                test_name=o.test_name.strip(), loinc_code=o.loinc_code,
                # The display text always comes from the LOINC table so code and display stay consistent.
                loinc_display=loinc.get_concept(o.loinc_code)["display"],
                value=o.value, unit=o.unit, ref_low=o.ref_low, ref_high=o.ref_high,
                interpretation=interpret(o.value, o.ref_low, o.ref_high),
            )
            for o in data.observations
        ],
    )
    db.add(report)
    db.commit()
    audit(db, "REPORT_CREATED", "SUCCESS", user, report.patient_id, "Report", report.id,
          f"{len(report.observations)} observations")
    return report


@router.get("/reports", response_model=list[ReportSummary])
def list_reports(user: User = Depends(require_roles("LAB", "PATIENT")), db: Session = Depends(get_db)):
    query = select(Report).order_by(Report.issued_at.desc()).limit(200)
    if user.role == "LAB":
        query = query.where(Report.facility_id == user.facility_id)
    else:
        query = query.where(Report.patient_id == user.patient_id)
    return db.scalars(query).all()


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_visible_report(db, report_id, user)


@router.get("/reports/{report_id}/fhir")
def get_report_fhir(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The report as a FHIR document Bundle, plus base-R4 validation results."""
    report = get_visible_report(db, report_id, user)
    return fhir.with_validation(fhir.report_bundle(report))


@router.post("/reports/{report_id}/withdraw", response_model=ReportOut)
def withdraw_report(report_id: int, user: User = Depends(require_roles("LAB")), db: Session = Depends(get_db)):
    """Mark a report as entered in error. It stays stored but can no longer be shared."""
    report = get_visible_report(db, report_id, user)
    if report.status == "entered-in-error":
        raise HTTPException(409, "Report is already withdrawn")
    report.status = "entered-in-error"
    db.commit()
    audit(db, "REPORT_WITHDRAWN", "SUCCESS", user, report.patient_id, "Report", report.id)
    return report
