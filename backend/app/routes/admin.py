import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AccessRequest, AuditEvent, Consent, Consultation, Facility, Patient, Report, User
from ..schemas import AuditOut, FacilityIn, FacilityOut, UserCreate, UserOut, UserUpdate
from ..security import get_current_user, hash_password, require_roles
from ..services import audit

router = APIRouter(tags=["admin"])
admin_only = require_roles("ADMIN")


@router.get("/admin/stats")
def stats(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where))

    return {
        "users": count(User),
        "facilities": count(Facility),
        "patients": count(Patient),
        "reports": count(Report),
        "consultations": count(Consultation),
        "access_requests": count(AccessRequest),
        "consents_by_status": dict(db.execute(select(Consent.status, func.count()).group_by(Consent.status)).all()),
        "denied_events": count(AuditEvent, AuditEvent.outcome != "SUCCESS"),
    }


@router.get("/admin/users", response_model=list[UserOut])
def list_users(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.role, User.username)).all()


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "That username is already taken")
    facility = db.get(Facility, data.facility_id) if data.facility_id else None
    if data.role in ("LAB", "HOSPITAL") and (facility is None or facility.facility_type != data.role):
        raise HTTPException(422, f"A {data.role} user needs a facility of type {data.role}")
    if data.role == "ADMIN" and data.facility_id:
        raise HTTPException(422, "Admin users do not belong to a facility")
    user = User(username=data.username, password_hash=hash_password(data.password), full_name=data.full_name,
                role=data.role, facility_id=facility.id if facility else None)
    db.add(user)
    db.commit()
    audit(db, "ADMIN_USER_CREATED", "SUCCESS", admin, resource_type="User", resource_id=user.id, detail=user.role)
    return user


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and data.is_active is False:
        raise HTTPException(409, "You cannot deactivate your own account")
    changes = []
    if data.full_name is not None:
        user.full_name = data.full_name
        changes.append("name")
    if data.is_active is not None:
        user.is_active = data.is_active
        changes.append("activated" if data.is_active else "deactivated")
    if data.password is not None:
        user.password_hash = hash_password(data.password)
        user.token_version += 1  # sign the user out everywhere
        changes.append("password reset")
    db.commit()
    audit(db, "ADMIN_USER_UPDATED", "SUCCESS", admin, resource_type="User", resource_id=user.id,
          detail=", ".join(changes) or "no changes")
    return user


@router.post("/facilities", response_model=FacilityOut, status_code=201)
def create_facility(data: FacilityIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(Facility).where(func.lower(Facility.name) == data.name.strip().lower())):
        raise HTTPException(409, "A facility with this name already exists")
    facility = Facility(name=data.name.strip(), facility_type=data.facility_type, city=data.city.strip(),
                        facility_code="TMP-" + secrets.token_hex(6))
    db.add(facility)
    db.flush()
    facility.facility_code = f"FAC-{data.facility_type}-{facility.id:03d}"
    db.commit()
    audit(db, "ADMIN_FACILITY_CREATED", "SUCCESS", admin, resource_type="Facility", resource_id=facility.id)
    return facility


@router.get("/audit-events", response_model=list[AuditOut])
def audit_events(event_type: str = "", outcome: str = "", patient_id: int | None = None, limit: int = 200,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admins see everything; patients see only events about their own record."""
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(max(limit, 1), 1000))
    if user.role == "PATIENT":
        query = query.where(AuditEvent.patient_id == user.patient_id)
    elif user.role != "ADMIN":
        raise HTTPException(403, "Your role is not allowed to do this")
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    if outcome:
        query = query.where(AuditEvent.outcome == outcome)
    if patient_id is not None:
        query = query.where(AuditEvent.patient_id == patient_id)
    return db.scalars(query).all()
