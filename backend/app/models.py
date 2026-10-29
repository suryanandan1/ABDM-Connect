"""SQLAlchemy models: the 10 tables of ABDM Connect."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, UTCDateTime, utcnow

ROLES = ("ADMIN", "PATIENT", "LAB", "HOSPITAL")
FACILITY_TYPES = ("LAB", "HOSPITAL")
CONSENT_STATUSES = ("PENDING", "ACTIVE", "DENIED", "EXPIRED", "REVOKED")
# Purpose codes from the HL7 v3 PurposeOfUse value set (not ABDM-specific codes).
PURPOSES = {
    "TREAT": "Treatment",
    "ETREAT": "Emergency treatment",
    "PUBHLTH": "Public health",
    "HRESCH": "Healthcare research",
}


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (CheckConstraint("facility_type IN ('LAB','HOSPITAL')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_code: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. FAC-LAB-001
    name: Mapped[str] = mapped_column(String(120), unique=True)
    facility_type: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (CheckConstraint("gender IN ('male','female','other','unknown')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(String(30), unique=True)  # e.g. PAT-000001 (not an ABHA number)
    full_name: Mapped[str] = mapped_column(String(120))
    gender: Mapped[str] = mapped_column(String(10))
    birth_date: Mapped[date] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(20))
    registered_by_facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    registered_by: Mapped[Facility | None] = relationship()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN','PATIENT','LAB','HOSPITAL')"),
        # Lab and hospital staff must belong to a facility; patients must link to a patient record.
        CheckConstraint("role NOT IN ('LAB','HOSPITAL') OR facility_id IS NOT NULL", name="staff_has_facility"),
        CheckConstraint("role != 'PATIENT' OR patient_id IS NOT NULL", name="patient_has_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(10))
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Increased on logout / password reset; tokens carrying an older version stop working.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    facility: Mapped[Facility | None] = relationship()
    patient: Mapped[Patient | None] = relationship()


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("status IN ('final','amended','entered-in-error')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(120))
    panel_loinc_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="final")
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    conclusion: Mapped[str | None] = mapped_column(String(500))

    patient: Mapped[Patient] = relationship()
    facility: Mapped[Facility] = relationship()
    created_by: Mapped[User] = relationship()
    observations: Mapped[list["Observation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="Observation.id"
    )


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("report_id", "loinc_code"),  # one result per test per report
        CheckConstraint("ref_low IS NULL OR ref_high IS NULL OR ref_low <= ref_high"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    test_name: Mapped[str] = mapped_column(String(120))  # name used by the lab
    loinc_code: Mapped[str] = mapped_column(String(20))
    loinc_display: Mapped[str] = mapped_column(String(255))  # always copied from the LOINC table
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))  # UCUM code
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    interpretation: Mapped[str | None] = mapped_column(String(2))  # L, N or H

    report: Mapped[Report] = relationship(back_populates="observations")


class Consultation(Base):
    """An outpatient consultation written by a hospital doctor (like an ABDM OP Consultation Record)."""
    __tablename__ = "consultations"
    __table_args__ = (
        CheckConstraint("status IN ('final','entered-in-error')"),
        CheckConstraint("bp_systolic IS NULL OR bp_diastolic IS NULL OR bp_systolic > bp_diastolic"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    doctor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="final")
    visit_at: Mapped[datetime] = mapped_column(UTCDateTime)
    chief_complaint: Mapped[str] = mapped_column(String(500))
    examination: Mapped[str | None] = mapped_column(String(1000))
    diagnosis: Mapped[str] = mapped_column(String(300))
    advice: Mapped[str | None] = mapped_column(String(1000))
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    # Optional vital signs, stored in the UCUM units shown next to each name.
    bp_systolic: Mapped[int | None] = mapped_column(Integer)  # mm[Hg]
    bp_diastolic: Mapped[int | None] = mapped_column(Integer)  # mm[Hg]
    pulse: Mapped[int | None] = mapped_column(Integer)  # /min
    temperature: Mapped[float | None] = mapped_column(Float)  # Cel
    spo2: Mapped[int | None] = mapped_column(Integer)  # %
    weight: Mapped[float | None] = mapped_column(Float)  # kg
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    patient: Mapped[Patient] = relationship()
    facility: Mapped[Facility] = relationship()
    doctor: Mapped[User] = relationship()
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan", order_by="Medication.id"
    )


class Medication(Base):
    """One prescribed medicine. Free text until a drug terminology is integrated."""
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    dosage: Mapped[str] = mapped_column(String(60))  # e.g. "1 tablet (500 mg)"
    frequency: Mapped[str] = mapped_column(String(60))  # e.g. "Twice a day"
    duration: Mapped[str] = mapped_column(String(60))  # e.g. "5 days"
    instructions: Mapped[str | None] = mapped_column(String(200))  # e.g. "After food"

    consultation: Mapped[Consultation] = relationship(back_populates="medications")


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACTIVE','DENIED','EXPIRED','REVOKED')"),
        CheckConstraint("duration_days BETWEEN 1 AND 30"),
        # The data scope is exactly one record: a lab report OR a doctor consultation.
        CheckConstraint("(report_id IS NULL) != (consultation_id IS NULL)", name="consent_one_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    requester_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))
    purpose: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    duration_days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    patient: Mapped[Patient] = relationship()
    requester_facility: Mapped[Facility] = relationship()
    report: Mapped[Report | None] = relationship()
    consultation: Mapped[Consultation | None] = relationship()


class AccessRequest(Base):
    """An HIU's request for one record held by an HIP. A hospital can be on either side."""
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("(report_id IS NULL) != (consultation_id IS NULL)", name="request_one_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requester_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"))
    purpose: Mapped[str] = mapped_column(String(10))
    consent_id: Mapped[int] = mapped_column(ForeignKey("consents.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    requester: Mapped[User] = relationship()
    requester_facility: Mapped[Facility] = relationship()
    patient: Mapped[Patient] = relationship()
    report: Mapped[Report | None] = relationship()
    consultation: Mapped[Consultation | None] = relationship()
    consent: Mapped[Consent] = relationship()

    @property
    def record(self):
        """The requested record (report or consultation)."""
        return self.report or self.consultation

    @property
    def status(self):
        # The request has no separate status: it always shows its consent's status.
        return self.consent.status


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint("outcome IN ('SUCCESS','DENIED','FAILURE')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(10))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_username: Mapped[str | None] = mapped_column(String(50))
    actor_role: Mapped[str | None] = mapped_column(String(10))
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(30))
    resource_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(String(255))  # short, never medical values
