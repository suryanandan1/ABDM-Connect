from conftest import login


def test_login_success_and_me(client):
    h = login(client, "lab1")
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["role"] == "LAB" and me["facility"]["facility_code"] == "FAC-LAB-001"
    assert "password_hash" not in me


def test_login_wrong_password_is_rejected_and_audited(client):
    r = client.post("/api/v1/auth/login", json={"username": "lab1", "password": "wrong-password"})
    assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401
    events = client.get("/api/v1/audit-events?event_type=LOGIN&outcome=FAILURE", headers=login(client, "admin")).json()
    assert {e["actor_username"] for e in events} >= {"lab1", "nobody"}
    assert all("wrong-password" not in (e["detail"] or "") for e in events)


def test_missing_and_bad_tokens(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_logout_invalidates_token(client):
    h = login(client, "hospital1")
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_deactivated_user_cannot_log_in(client):
    admin = login(client, "admin")
    users = client.get("/api/v1/admin/users", headers=admin).json()
    lab2 = next(u for u in users if u["username"] == "lab2")
    assert client.patch(f"/api/v1/admin/users/{lab2['id']}", json={"is_active": False}, headers=admin).status_code == 200
    r = client.post("/api/v1/auth/login", json={"username": "lab2", "password": "Connect@2026"})
    assert r.status_code == 401


def test_role_permissions(client):
    hospital, patient, lab = login(client, "hospital1"), login(client, "asha"), login(client, "lab1")
    # Only labs register patients and create reports
    new_patient = {"full_name": "X Y", "gender": "male", "birth_date": "2000-01-01", "username": "xy1", "password": "Password1"}
    assert client.post("/api/v1/patients", json=new_patient, headers=hospital).status_code == 403
    assert client.post("/api/v1/reports", json={}, headers=patient).status_code in (403, 422)
    # Only admins use admin endpoints
    assert client.get("/api/v1/admin/users", headers=lab).status_code == 403
    assert client.get("/api/v1/admin/stats", headers=hospital).status_code == 403
    # Hospitals and labs cannot read the audit log
    assert client.get("/api/v1/audit-events", headers=hospital).status_code == 403
    # Only patients decide on consent
    assert client.post("/api/v1/consents/1/approve", headers=hospital).status_code == 403


def test_admin_creates_user_and_facility(client):
    admin = login(client, "admin")
    f = client.post("/api/v1/facilities", json={"name": "New City Hospital", "facility_type": "HOSPITAL", "city": "Delhi"},
                    headers=admin)
    assert f.status_code == 201 and f.json()["facility_code"].startswith("FAC-HOSPITAL-")
    u = client.post("/api/v1/admin/users", json={"username": "doc9", "password": "Password9", "full_name": "Doc Nine",
                                                  "role": "HOSPITAL", "facility_id": f.json()["id"]}, headers=admin)
    assert u.status_code == 201
    # Wrong facility type is rejected
    bad = client.post("/api/v1/admin/users", json={"username": "doc10", "password": "Password9", "full_name": "Doc Ten",
                                                    "role": "LAB", "facility_id": f.json()["id"]}, headers=admin)
    assert bad.status_code == 422
    assert login(client, "doc9", "Password9")


def test_expired_token_is_rejected(client):
    from datetime import timedelta

    import jwt

    from app.config import JWT_SECRET
    from app.database import utcnow

    token = jwt.encode({"sub": "1", "ver": 0, "exp": utcnow() - timedelta(minutes=1)}, JWT_SECRET, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
