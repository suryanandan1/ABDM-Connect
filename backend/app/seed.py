"""Create the database tables and load sample data for development and testing.

Run from the backend folder:   python -m app.seed          (only adds data to an empty database)
                               python -m app.seed --reset  (deletes everything and starts again)
                               python -m app.seed --extra  (also adds more hospitals, doctors and patients;
                                                            works on an existing database, can be combined with --reset)
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


# ---------- Extra sample data (python -m app.seed --extra) ----------
# More hospitals, several doctors per hospital, more patients, visits and reports. Kept apart from
# seed() because the tests and tools/e2e_acceptance.py rely on the small data set above.
# Some patients match identities in ../mock_abdm/holders.json to try ABHA linking.

EXTRA_FACILITIES = [  # name, type, city
    ("City Care Multispeciality Hospital", "HOSPITAL", "Bengaluru"),
    ("Sanjeevani Hospital", "HOSPITAL", "Lucknow"),
    ("Harbour Heart Institute", "HOSPITAL", "Mumbai"),
    ("Apex Pathology", "LAB", "Hyderabad"),
]
EXTRA_STAFF = {  # facility name -> [(username, full name)]; hospital staff are doctors
    "Green Valley Hospital": [("gvh.sanjay", "Dr. Sanjay Malhotra"), ("gvh.pooja", "Dr. Pooja Nair")],
    "Lakeside Hospital": [("lsh.thomas", "Dr. Thomas Varghese"), ("lsh.anjali", "Dr. Anjali Menon")],
    "City Care Multispeciality Hospital": [
        ("cch.rahul", "Dr. Rahul Deshpande"), ("cch.sneha", "Dr. Sneha Kulkarni"), ("cch.farhan", "Dr. Farhan Ali")],
    "Sanjeevani Hospital": [
        ("sjh.alok", "Dr. Alok Tripathi"), ("sjh.ritu", "Dr. Ritu Srivastava"), ("sjh.manoj", "Dr. Manoj Yadav")],
    "Harbour Heart Institute": [("hhi.zubin", "Dr. Zubin Patel"), ("hhi.kavya", "Dr. Kavya Joshi")],
    "Apex Pathology": [("apx.suresh", "Suresh Babu"), ("apx.divya", "Divya Rao")],
}
EXTRA_PATIENTS = [  # username, full name, gender, birth date, phone, registered at, ABHA number, ABHA address
    ("neha", "Neha Gupta", "female", date(1992, 7, 21), "9811000001", "Sunrise Diagnostics", None, None),
    ("lakshmi", "Lakshmi", "female", date(1952, 8, 19), "9811000002", "CityPath Labs", None, None),
    ("fatima", "Fatima Begum", "female", date(1968, 12, 1), "9800000008", "Apex Pathology",
     "91-1212-3434-5656", None),
    ("rohan", "Rohan Das", "male", date(1988, 2, 17), "9811000004", "Sunrise Diagnostics", None, None),
    ("sunita", "Sunita Devi", "female", date(1975, 6, 8), None, "CityPath Labs", None, None),
    ("irfan", "Mohammed Irfan", "male", date(1964, 1, 30), "9811000006", "Apex Pathology", None, None),
    ("ananya", "Ananya Iyer", "female", date(2005, 10, 11), "9811000007", "Sunrise Diagnostics", None, None),
    ("karan", "Karan Malhotra", "male", date(1997, 12, 24), "9811000008", "Apex Pathology", None, None),
    ("geeta", "Geeta Pillai", "female", date(1958, 4, 3), "9811000009", "CityPath Labs", None, None),
    ("joseph", "Joseph Fernandes", "male", date(1982, 9, 15), "9811000010", "Sunrise Diagnostics", None, None),
]
# patient username, doctor username, days ago, complaint, diagnosis, (bp_sys, bp_dia, pulse, temp, spo2, weight),
# advice, [(medicine, dosage, frequency, duration)]
EXTRA_CONSULTATIONS = [
    ("rohan", "cch.rahul", 20, "Chest discomfort on exertion for 1 week", "Stable angina, under evaluation",
     (146, 92, 84, 36.8, 98, 82.0), "Avoid heavy exertion. TMT and lipid profile advised.",
     [("Aspirin 75 mg tablet", "1 tablet", "Once a day", "30 days"),
      ("Atorvastatin 20 mg tablet", "1 tablet", "Once at night", "30 days")]),
    ("rohan", "hhi.zubin", 6, "Referred for cardiology opinion", "Stable angina; TMT positive",
     (138, 88, 78, 36.7, 99, 81.5), "Coronary angiography planned. Continue medicines.",
     [("Metoprolol 25 mg tablet", "1 tablet", "Twice a day", "30 days")]),
    ("sunita", "sjh.ritu", 12, "Tiredness and weight gain for 3 months", "Suspected hypothyroidism",
     (124, 80, 64, 36.5, 99, 71.0), "Thyroid function test advised.", []),
    ("sunita", "sjh.ritu", 3, "Review with thyroid report", "Primary hypothyroidism",
     (122, 78, 66, 36.6, 99, 70.4), "Take thyroxine on an empty stomach. Repeat TSH after 6 weeks.",
     [("Levothyroxine 50 mcg tablet", "1 tablet", "Once in the morning", "6 weeks")]),
    ("irfan", "sjh.alok", 9, "Increased thirst and frequent urination", "Type 2 diabetes mellitus",
     (142, 90, 82, 36.9, 97, 88.0), "Diabetic diet, 30 minutes walk daily. HbA1c after 3 months.",
     [("Metformin 500 mg tablet", "1 tablet", "Twice a day after food", "90 days")]),
    ("ananya", "gvh.pooja", 4, "Fever with body ache for 3 days", "Viral fever",
     (110, 70, 96, 38.6, 98, 52.0), "Fluids and rest. Return if fever lasts more than 5 days.",
     [("Paracetamol 650 mg tablet", "1 tablet", "Three times a day", "3 days")]),
    ("geeta", "lsh.anjali", 15, "Knee pain while climbing stairs", "Osteoarthritis of both knees",
     (134, 84, 72, 36.6, 98, 68.0), "Knee strengthening exercises, weight control.",
     [("Paracetamol 500 mg tablet", "1 tablet", "Twice a day when needed", "10 days")]),
    ("karan", "cch.farhan", 2, "Cough with wheeze at night", "Mild persistent asthma",
     (118, 76, 88, 36.9, 95, 74.0), "Avoid dust and smoke. Inhaler technique explained.",
     [("Budesonide-formoterol 200/6 inhaler", "1 puff", "Twice a day", "30 days")]),
    ("joseph", "gvh.sanjay", 7, "Burning pain in upper abdomen after meals", "Gastritis",
     (126, 82, 76, 36.7, 99, 79.0), "Avoid spicy food, alcohol and late meals.",
     [("Pantoprazole 40 mg tablet", "1 tablet", "Once before breakfast", "14 days")]),
    ("lakshmi", "lsh.thomas", 10, "Giddiness on standing", "Postural hypotension",
     (104, 64, 80, 36.5, 97, 49.0), "Get up slowly, drink enough water.", []),
]
# patient username, lab staff username, days ago, title, conclusion, [(test name, LOINC, value, unit, low, high)]
EXTRA_REPORTS = [
    ("rohan", "lab1", 18, "Lipid Profile", "Total cholesterol above reference range.",
     [("Total Cholesterol", "2093-3", 236, "mg/dL", 0, 200)]),
    ("sunita", "lab2", 8, "Thyroid Function", "TSH raised, consistent with hypothyroidism.",
     [("TSH", "3016-3", 9.8, "m[IU]/L", 0.4, 4.0)]),
    ("irfan", "apx.suresh", 10, "Diabetes Screening", "Fasting glucose and HbA1c in diabetic range.",
     [("Fasting Blood Sugar", "1558-6", 168, "mg/dL", 70, 100), ("HbA1c", "4548-4", 8.1, "%", 4.0, 5.6)]),
    ("geeta", "lab2", 16, "Kidney and Liver Function", "Within reference ranges.",
     [("Creatinine", "2160-0", 0.9, "mg/dL", 0.5, 1.1), ("ALT (SGPT)", "1742-6", 28, "U/L", 7, 56)]),
    ("ananya", "lab1", 4, "Haemoglobin", "Mild anaemia.",
     [("Hemoglobin", "718-7", 10.9, "g/dL", 12, 15.5)]),
    ("fatima", "apx.divya", 5, "Random Blood Sugar", "Within reference range.",
     [("Random Blood Sugar", "2345-7", 128, "mg/dL", 70, 140)]),
]


def seed_extra():
    """Add the extra sample data to a database that already has the basic sample data. Safe to run twice."""
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="lab1").count():
            print("Load the basic sample data first: python -m app.seed")
            return
        if db.query(Facility).filter_by(name=EXTRA_FACILITIES[0][0]).count():
            print("Extra sample data is already loaded.")
            return
        wanted = [u for staff in EXTRA_STAFF.values() for u, _ in staff] + [p[0] for p in EXTRA_PATIENTS]
        taken = [u for (u,) in db.query(User.username).filter(User.username.in_(wanted))]
        if taken:
            print(f"Cannot load extra data, these usernames already exist: {', '.join(taken)}")
            return

        for name, kind, city in EXTRA_FACILITIES:
            facility = Facility(facility_code="TMP-" + name, name=name, facility_type=kind, city=city)
            db.add(facility)
            db.flush()
            facility.facility_code = f"FAC-{kind}-{facility.id:03d}"  # same format as the admin screen
        facilities = {f.name: f for f in db.query(Facility)}

        pw = hash_password(SAMPLE_PASSWORD)
        users = {u.username: u for u in db.query(User)}
        for facility_name, staff in EXTRA_STAFF.items():
            facility = facilities.get(facility_name)
            if facility is None:  # an original sample facility was renamed or removed
                continue
            for username, full_name in staff:
                users[username] = User(username=username, password_hash=pw, full_name=full_name,
                                       role=facility.facility_type, facility=facility)
                db.add(users[username])

        patients = {}
        for username, name, gender, born, phone, registered_at, abha_number, abha_address in EXTRA_PATIENTS:
            patient = Patient(patient_code="TMP-" + username, full_name=name, gender=gender, birth_date=born, phone=phone,
                              registered_by=facilities.get(registered_at), abha_number=abha_number,
                              abha_address=abha_address, abha_verified_at=utcnow() if abha_number else None)
            db.add(patient)
            db.flush()
            patient.patient_code = f"PAT-{patient.id:06d}"
            patients[username] = patient
            db.add(User(username=username, password_hash=pw, full_name=name, role="PATIENT", patient=patient))
        db.flush()

        for who, doctor, days, complaint, diagnosis, vitals, advice, meds in EXTRA_CONSULTATIONS:
            if doctor not in users:
                continue
            sys_, dia, pulse, temp, spo2, weight = vitals
            db.add(Consultation(
                patient=patients[who], facility=users[doctor].facility, doctor=users[doctor],
                visit_at=utcnow() - timedelta(days=days), chief_complaint=complaint, diagnosis=diagnosis,
                bp_systolic=sys_, bp_diastolic=dia, pulse=pulse, temperature=temp, spo2=spo2, weight=weight,
                advice=advice, medications=[Medication(name=n, dosage=d, frequency=f, duration=t) for n, d, f, t in meds],
            ))
        for who, author, days, title, conclusion, results in EXTRA_REPORTS:
            if author not in users:
                continue
            db.add(Report(
                patient=patients[who], facility=users[author].facility, created_by=users[author], title=title,
                collected_at=utcnow() - timedelta(days=days), conclusion=conclusion,
                observations=[Observation(
                    test_name=test, loinc_code=code, loinc_display=get_concept(code)["display"], value=value, unit=unit,
                    ref_low=low, ref_high=high, interpretation="H" if value > high else "L" if value < low else "N",
                ) for test, code, value, unit, low, high in results],
            ))
        db.commit()
    finally:
        db.close()

    print(f"Extra sample data added. Every account uses the password {SAMPLE_PASSWORD}")
    for facility_name, staff in EXTRA_STAFF.items():
        print(f"  {facility_name}: {', '.join(u for u, _ in staff)}")
    print(f"  Patients: {', '.join(p[0] for p in EXTRA_PATIENTS)}")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    upgrade()
    seed()
    if "--extra" in sys.argv:
        seed_extra()
