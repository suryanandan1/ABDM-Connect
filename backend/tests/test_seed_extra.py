from app.seed import EXTRA_PATIENTS, seed_extra
from conftest import login


def test_extra_sample_data_loads_once(client, capsys):
    seed_extra()
    seed_extra()
    assert "already loaded" in capsys.readouterr().out
    admin = login(client, "admin")
    hospitals = [f for f in client.get("/api/v1/facilities", headers=admin).json() if f["facility_type"] == "HOSPITAL"]
    assert len(hospitals) == 5
    users = client.get("/api/v1/admin/users", headers=admin).json()
    doctors_at_city_care = [u["username"] for u in users if u["facility"] and u["facility"]["name"] == "City Care Multispeciality Hospital"]
    assert sorted(doctors_at_city_care) == ["cch.farhan", "cch.rahul", "cch.sneha"]
    assert len(client.get("/api/v1/patients", headers=admin).json()) == 2 + len(EXTRA_PATIENTS)


def test_doctors_of_one_hospital_share_its_consultations(client):
    seed_extra()
    seen = [{c["id"] for c in client.get("/api/v1/consultations", headers=login(client, u)).json()}
            for u in ("cch.rahul", "cch.farhan")]
    assert seen[0] and seen[0] == seen[1]
    # A patient sees only their own visits, from several hospitals.
    rohan = client.get("/api/v1/consultations", headers=login(client, "rohan")).json()
    assert len(rohan) == 2
