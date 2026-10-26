from datetime import datetime, timedelta

from app.core.security import create_access_token
from tests.conftest import PASSWORD, login


def test_login_success_returns_token_user_and_permissions(client, world):
    r = client.post("/api/v1/auth/login", json={"username": "a_manager", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["company_name"] == "Company A"
    assert "Customer.Assign" in body["user"]["permissions"]
    assert "fs_access" in r.cookies and "fs_csrf" in r.cookies
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "a_manager"


def test_invalid_password_is_401_without_user_enumeration(client, world):
    bad_pw = client.post("/api/v1/auth/login", json={"username": "a_manager", "password": "nope"})
    no_user = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "nope"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


def test_inactive_and_suspended_users_cannot_login(client, world, db):
    world.a_sales1.status = "Inactive"
    world.a_sales2.status = "Suspended"
    db.commit()
    assert client.post("/api/v1/auth/login", json={"username": "a_sales1", "password": PASSWORD}).status_code == 403
    assert client.post("/api/v1/auth/login", json={"username": "a_sales2", "password": PASSWORD}).status_code == 403


def test_existing_token_stops_working_when_user_is_suspended(client, world, db, h):
    headers = h["a_sales1"]
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    world.a_sales1.status = "Suspended"
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403


def test_expired_token_rejected(client, world):
    token, _, _ = create_access_token(world.a_manager.id, world.a.id, expires_minutes=-1)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "expired" in r.json()["error"]["message"].lower()


def test_tampered_or_missing_token_rejected(client, world):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_token_company_claim_must_match_user(client, world):
    token, _, _ = create_access_token(world.a_manager.id, world.b.id)  # forged company claim
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_rate_limit(client, world):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"username": "a_admin", "password": "wrong"}).status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "a_admin", "password": PASSWORD})
    assert r.status_code == 429


def test_logout_revokes_token(client, world):
    headers = login(client, "a_admin")
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_cookie_auth_requires_csrf_header_on_unsafe_methods(client, world):
    r = client.post("/api/v1/auth/login", json={"username": "a_admin", "password": PASSWORD})
    csrf = r.cookies["fs_csrf"]
    assert client.get("/api/v1/auth/me").status_code == 200  # cookie only, safe method
    assert client.put("/api/v1/auth/me", json={"full_name": "X Y"}).status_code == 403
    ok = client.put("/api/v1/auth/me", json={"full_name": "X Y"}, headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 200 and ok.json()["full_name"] == "X Y"


def test_change_password(client, world):
    headers = login(client, "a_admin")
    r = client.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "NewPass123"}, headers=headers)
    assert r.status_code == 204
    assert client.post("/api/v1/auth/login", json={"username": "a_admin", "password": "NewPass123"}).status_code == 200
    weak = client.post("/api/v1/auth/change-password", json={"current_password": "NewPass123", "new_password": "short"}, headers=headers)
    assert weak.status_code == 422


def test_backend_enforces_permissions_not_just_ui(client, world, h):
    assert client.get("/api/v1/users", headers=h["a_sales1"]).status_code == 403
    r = client.post("/api/v1/customers", json={"name": "X", "mobile": "+971500000123", "city": "Dubai"}, headers=h["a_sales1"])
    assert r.status_code == 403  # salesmen create customers only through the Visit workflow
    assert client.get("/api/v1/reports/visits", headers=h["a_sales1"]).status_code == 403
