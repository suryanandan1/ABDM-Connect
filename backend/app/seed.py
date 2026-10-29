"""Create the database tables and load sample data for development and testing.

Run from the backend folder:   python -m app.seed          (only adds data to an empty database)
                               python -m app.seed --reset  (deletes everything and starts again)
"""
import sys
from datetime import date, timedelta

from .loinc import get_concept
from .database import Base, SessionLocal, engine, utcnow
from .migrations import upgrade
from .models import Consultation, Facility, Medication, Observation, Patient, Report, User
from .security import hash_password

SAMPLE_PASSWORD = "Connect@2026"  # development and testing only - never use these accounts in production


def seed():
    db = SessionLocal()
    if db.query(User).count():
        print("Database already has data. Use --reset to start again.")
        return
    lab1 = Facility(facility_code="FAC-LAB-001", name="Sunrise Diagnostics", facility_type="LAB", city="Pune")
    lab2 = Facility(facility_code="FAC-LAB-002", name="CityPath Labs", facility_type="LAB", city="Jaipur")
    hosp1 = Facility(facility_code="FAC-HOSPITAL-003", name="Green Valley Hospital",
                     facility_type="HOSPITAL", city="Gurugram")
    hosp2 = Facility(facility_code="FAC-HOSPITAL-004", name="Lakeside Hospital",
                     facility_type="HOSPITAL", city="Kochi")
    asha = Patient(patient_code="PAT-000001", full_name="Asha Verma", gender="female",
                   birth_date=date(1990, 5, 14), phone="9000000001", registered_by=lab1)
    ravi = Patient(patient_code="PAT-000002", full_name="Ravi Kumar", gender="male",
                   birth_date=date(1985, 11, 2), phone="9000000002", registered_by=lab2)
    pw = hash_password(SAMPLE_PASSWORD)
    lab_user = User(username="lab1", password_hash=pw, full_name="Dr. Meera Iyer", role="LAB", facility=lab1)
    users = [
        User(username="admin", password_hash=pw, full_name="System Administrator", role="ADMIN"),
        lab_user,
        User(username="lab2", password_hash=pw, full_name="Dr. Arjun Shah", role="LAB", facility=lab2),
        User(username="hospital1", password_hash=pw, full_name="Dr. Kavita Rao", role="HOSPITAL", facility=hosp1),
        User(username="hospital2", password_hash=pw, full_name="Dr. Imran Khan", role="HOSPITAL", facility=hosp2),
        User(username="asha", password_hash=pw, full_name=asha.full_name, role="PATIENT", patient=asha),
        User(username="ravi", password_hash=pw, full_name=ravi.full_name, role="PATIENT", patient=ravi),
    ]
    db.add_all(users)
    db.flush()
    # One sample glucose report so the patient and hospital screens are not empty.
    db.add(Report(
        patient=asha, facility=lab1, created_by=lab_user, title="Blood Glucose",
        collected_at=utcnow() - timedelta(days=3), conclusion="Fasting glucose within reference range.",
        observations=[
            Observation(test_name="Fasting Blood Sugar", loinc_code="1558-6",
                        loinc_display=get_concept("1558-6")["display"],
                        value=92, unit="mg/dL", ref_low=70, ref_high=100, interpretation="N"),
            Observation(test_name="HbA1c", loinc_code="4548-4", loinc_display=get_concept("4548-4")["display"],
                        value=5.4, unit="%", ref_low=4.0, ref_high=5.6, interpretation="N"),
        ],
    ))
    # One sample doctor consultation so the patient can see a visit summary.
    db.add(Consultation(
        patient=asha, facility=hosp1, doctor=users[3], visit_at=utcnow() - timedelta(days=2),
        chief_complaint="Fever and sore throat for 2 days",
        examination="Throat congested, tonsils mildly enlarged. Chest clear.",
        diagnosis="Acute pharyngitis", bp_systolic=118, bp_diastolic=76, pulse=88, temperature=38.2, spo2=98,
        advice="Warm saline gargles, plenty of fluids and rest. Return earlier if fever persists beyond 3 days.",
        follow_up_date=(utcnow() + timedelta(days=5)).date(),
        medications=[
            Medication(name="Paracetamol 500 mg tablet", dosage="1 tablet", frequency="Three times a day",
                       duration="3 days", instructions="After food, only if fever"),
            Medication(name="Cetirizine 10 mg tablet", dosage="1 tablet", frequency="Once at night", duration="5 days"),
        ],
    ))
    db.commit()
    print(f"Sample data created. Every sample account uses the password {SAMPLE_PASSWORD}")
    for u in users:
        print(f"  {u.username:<10} {u.role}")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    upgrade()
    seed()
