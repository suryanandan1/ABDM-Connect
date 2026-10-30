"""Pydantic models for request validation and response shapes."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .database import utcnow
from .loinc import ALLOWED_UNITS

# Must match models.PURPOSES
Purpose = Literal["TREAT", "ETREAT", "PUBHLTH", "HRESCH"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- facilities and users ----------
class FacilityIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    facility_type: Literal["LAB", "HOSPITAL"]
    city: str = Field(default="", max_length=80)


class FacilityOut(ORM):
    id: int
    facility_code: str
    name: str
    facility_type: str
    city: str


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    role: str
    facility_id: int | None
    patient_id: int | None
    is_active: bool
    facility: FacilityOut | None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["ADMIN", "LAB", "HOSPITAL"]  # patient logins are created with patient registration
    facility_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class LoginIn(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ---------- patients ----------
class PatientIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    gender: Literal["male", "female", "other", "unknown"]
    birth_date: date
    phone: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    # Login for the patient portal. The lab gives the patient this temporary password.
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)

    @field_validator("birth_date")
    @classmethod
    def not_in_future(cls, v):
        if v > date.today() or v.year < 1900:
            raise ValueError("birth date must be between 1900 and today")
        return v


class PatientOut(ORM):
    id: int
    patient_code: str
    full_name: str
    gender: str
    birth_date: date
    phone: str | None
    abha_number: str | None
    abha_address: str | None
    abha_verified_at: datetime | None
    created_at: datetime


class PatientBrief(ORM):
    id: int
    patient_code: str
    full_name: str


# ---------- ABHA verification (mock ABDM) ----------
class AbhaInitIn(BaseModel):
    abha_number: str | None = Field(default=None, pattern=r"^\s*\d{2}-?\d{4}-?\d{4}-?\d{4}\s*$")
    abha_address: str | None = Field(default=None, pattern=r"^\s*[a-zA-Z0-9_.]{3,}@[a-z]+\s*$")

    @model_validator(mode="after")
    def exactly_one(self):
        if bool(self.abha_number) == bool(self.abha_address):
            raise ValueError("enter either an ABHA number or an ABHA address")
        return self


class AbhaInitOut(BaseModel):
    txn_id: str
    message: str


class AbhaVerifyIn(BaseModel):
    txn_id: str = Field(min_length=1, max_length=64)
    otp: str = Field(pattern=r"^[0-9]{6}$")


class AbhaProfile(BaseModel):
    abha_number: str
    abha_address: str | None
    full_name: str
    gender: str
    birth_date: date
    phone: str | None


class AbhaVerifyOut(BaseModel):
    # Signed copy of the verified profile; sent back to register/link so the profile cannot be edited.
    abha_token: str
    profile: AbhaProfile
    existing_patient: PatientOut | None  # already registered with this ABHA
    possible_match: PatientOut | None  # same name + birth date, no ABHA yet: link instead of creating


class AbhaRegisterIn(BaseModel):
    abha_token: str
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)


class AbhaLinkIn(BaseModel):
    abha_token: str


# ---------- reports ----------
class ObservationIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    test_name: str = Field(min_length=1, max_length=120)
    loinc_code: str = Field(max_length=20)
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None

    @field_validator("unit")
    @classmethod
    def known_unit(cls, v):
        if v not in ALLOWED_UNITS:
            raise ValueError(f"unit must be one of: {', '.join(sorted(ALLOWED_UNITS))}")
        return v

    @model_validator(mode="after")
    def check_range(self):
        if self.ref_low is not None and self.ref_high is not None and self.ref_low > self.ref_high:
            raise ValueError("reference range low must not be greater than high")
        if self.value < 0:
            raise ValueError("result value cannot be negative")
        return self


class ReportIn(BaseModel):
    patient_id: int
    title: str = Field(min_length=2, max_length=120)
    panel_loinc_code: str | None = None
    collected_at: datetime
    conclusion: str | None = Field(default=None, max_length=500)
    observations: list[ObservationIn] = Field(min_length=1, max_length=30)

    @field_validator("collected_at")
    @classmethod
    def collected_in_past(cls, v):
        if v.tzinfo is None:
            raise ValueError("collected_at must include a time zone")
        if v > utcnow():
            raise ValueError("collection time cannot be in the future")
        return v


class ObservationOut(ORM):
    id: int
    test_name: str
    loinc_code: str
    loinc_display: str
    value: float
    unit: str
    ref_low: float | None
    ref_high: float | None
    interpretation: str | None


class ReportSummary(ORM):
    id: int
    title: str
    status: str
    issued_at: datetime
    collected_at: datetime
    patient_id: int
    facility: FacilityOut


class ReportOut(ReportSummary):
    panel_loinc_code: str | None
    conclusion: str | None
    patient: PatientBrief
    observations: list[ObservationOut]


class ReportBrief(ORM):
    id: int
    title: str
    issued_at: datetime
    facility: FacilityOut


class DoctorOut(ORM):
    id: int
    full_name: str


class ConsultationBrief(ORM):
    """What may be shown before consent: when, where and by whom. Never the clinical content."""
    id: int
    visit_at: datetime
    status: str
    facility: FacilityOut
    doctor: DoctorOut


# ---------- consent and access ----------
class AccessRequestIn(BaseModel):
    report_id: int | None = None
    consultation_id: int | None = None
    purpose: Purpose
    duration_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def one_record(self):
        if (self.report_id is None) == (self.consultation_id is None):
            raise ValueError("request exactly one record: report_id or consultation_id")
        return self


class RetrieveIn(BaseModel):
    purpose: Purpose


class ConsentOut(ORM):
    id: int
    status: str
    purpose: str
    duration_days: int
    created_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    patient: PatientBrief
    requester_facility: FacilityOut
    report: ReportBrief | None
    consultation: ConsultationBrief | None


class AccessRequestOut(ORM):
    id: int
    status: str
    purpose: str
    created_at: datetime
    patient: PatientBrief
    report: ReportBrief | None
    consultation: ConsultationBrief | None
    requester_facility: FacilityOut
    consent: ConsentOut


class AuditOut(ORM):
    id: int
    created_at: datetime
    event_type: str
    outcome: str
    actor_username: str | None
    actor_role: str | None
    patient_id: int | None
    resource_type: str | None
    resource_id: int | None
    detail: str | None


# ---------- doctor consultations (OP consultation record) ----------
class MedicationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dosage: str = Field(min_length=1, max_length=60)
    frequency: str = Field(min_length=1, max_length=60)
    duration: str = Field(min_length=1, max_length=60)
    instructions: str | None = Field(default=None, max_length=200)


class ConsultationIn(BaseModel):
    patient_id: int
    visit_at: datetime
    chief_complaint: str = Field(min_length=2, max_length=500)
    examination: str | None = Field(default=None, max_length=1000)
    diagnosis: str = Field(min_length=2, max_length=300)
    advice: str | None = Field(default=None, max_length=1000)
    follow_up_date: date | None = None
    bp_systolic: int | None = Field(default=None, ge=50, le=260)
    bp_diastolic: int | None = Field(default=None, ge=30, le=160)
    pulse: int | None = Field(default=None, ge=20, le=250)
    temperature: float | None = Field(default=None, ge=30, le=45)
    spo2: int | None = Field(default=None, ge=50, le=100)
    weight: float | None = Field(default=None, ge=0.5, le=400)
    medications: list[MedicationIn] = Field(default=[], max_length=20)

    @field_validator("visit_at")
    @classmethod
    def visit_in_past(cls, v):
        if v.tzinfo is None:
            raise ValueError("visit_at must include a time zone")
        if v > utcnow():
            raise ValueError("visit time cannot be in the future")
        return v

    @model_validator(mode="after")
    def check_vitals_and_dates(self):
        if (self.bp_systolic is None) != (self.bp_diastolic is None):
            raise ValueError("enter both systolic and diastolic blood pressure, or neither")
        if self.bp_systolic is not None and self.bp_systolic <= self.bp_diastolic:
            raise ValueError("systolic blood pressure must be higher than diastolic")
        if self.follow_up_date and self.follow_up_date < self.visit_at.date():
            raise ValueError("follow-up date cannot be before the visit")
        return self


class MedicationOut(ORM):
    id: int
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: str | None


class ConsultationSummary(ORM):
    id: int
    status: str
    visit_at: datetime
    diagnosis: str
    patient: PatientBrief
    facility: FacilityOut
    doctor: DoctorOut


class ConsultationOut(ConsultationSummary):
    chief_complaint: str
    examination: str | None
    advice: str | None
    follow_up_date: date | None
    bp_systolic: int | None
    bp_diastolic: int | None
    pulse: int | None
    temperature: float | None
    spo2: int | None
    weight: float | None
    created_at: datetime
    medications: list[MedicationOut]
