"""Company isolation: nothing from company B is readable or writable by company A, and vice versa."""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Customer, FollowUp
from tests.conftest import assign, new_customer


def _b_followup(client, h, world):
    r = client.post("/api/v1/followups", json={"customer_id": world.b_customer.id, "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat()},
                    headers=h["b_admin"])
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_user_reads_only_own_company_customers(client, world, h):
    mine = new_customer(client, h["a_manager"])
    r = client.get("/api/v1/customers", headers=h["a_manager"])
    assert [c["id"] for c in r.json()["items"]] == [mine["id"]]
    r = client.get("/api/v1/customers", headers=h["b_admin"])
    assert [c["id"] for c in r.json()["items"]] == [world.b_customer.id]
    assert client.get(f"/api/v1/customers/{mine['id']}", headers=h["a_admin"]).status_code == 200


def test_cannot_read_or_modify_other_company_customer(client, world, h):
    cid = world.b_customer.id
    assert client.get(f"/api/v1/customers/{cid}", headers=h["a_admin"]).status_code == 404
    assert client.put(f"/api/v1/customers/{cid}", json={"name": "Hacked"}, headers=h["a_admin"]).status_code == 404
    assert client.patch(f"/api/v1/customers/{cid}/status", json={"status": "Inactive"}, headers=h["a_admin"]).status_code == 404
    assert client.delete(f"/api/v1/customers/{cid}", headers=h["a_admin"]).status_code == 404
    assert client.get(f"/api/v1/customers/{cid}/activity", headers=h["a_admin"]).status_code == 404
    assert client.post(f"/api/v1/customers/{cid}/assignments", json={"salesman_id": world.a_sales1.id}, headers=h["a_manager"]).status_code == 404


def test_cannot_create_visit_for_other_company_customer(client, world, h):
    r = client.post("/api/v1/visits", json={"customer_id": world.b_customer.id, "purpose": "x"}, headers=h["a_manager"])
    assert r.status_code == 404


def test_cannot_access_other_company_followup(client, world, h):
    fid = _b_followup(client, h, world)
    assert client.get(f"/api/v1/followups/{fid}", headers=h["a_admin"]).status_code == 404
    assert client.post(f"/api/v1/followups/{fid}/outcomes", json={"outcome_text": "x"}, headers=h["a_admin"]).status_code == 404
    assert client.post(f"/api/v1/followups/{fid}/complete", headers=h["a_admin"]).status_code == 404
    assert client.get(f"/api/v1/followups/{fid}/outcomes", headers=h["a_admin"]).status_code == 404
    assert client.get("/api/v1/followups", headers=h["a_admin"]).json()["total"] == 0


def test_cannot_create_followup_for_other_company_customer(client, world, h):
    r = client.post("/api/v1/followups", json={"customer_id": world.b_customer.id, "due_date": datetime.utcnow().isoformat()}, headers=h["a_manager"])
    assert r.status_code == 404


def test_client_supplied_company_id_is_ignored(client, world, h, db):
    r = client.post("/api/v1/customers", json={"name": "Sneaky", "mobile": "+971502222222", "city": "Dubai", "company_id": world.b.id},
                    headers=h["a_manager"])
    assert r.status_code == 201
    assert r.json()["company_id"] == world.a.id


def test_cannot_assign_customer_to_other_company_salesman(client, world, h):
    c = new_customer(client, h["a_manager"])
    r = client.post(f"/api/v1/customers/{c['id']}/assignments", json={"salesman_id": world.b_sales.id}, headers=h["a_manager"])
    assert r.status_code == 422


def test_users_roles_branches_are_company_scoped(client, world, h):
    ids = {u["id"] for u in client.get("/api/v1/users", headers=h["a_admin"]).json()["items"]}
    assert world.b_admin.id not in ids and world.a_admin.id in ids
    assert client.get(f"/api/v1/users/{world.b_admin.id}", headers=h["a_admin"]).status_code == 404
    assert client.put(f"/api/v1/users/{world.b_admin.id}", json={"full_name": "x"}, headers=h["a_admin"]).status_code == 404
    assert client.get(f"/api/v1/branches/{world.branch_b.id}", headers=h["a_admin"]).status_code == 404
    r = client.post("/api/v1/users", json={"username": "evil", "full_name": "E", "password": "Passw0rd1", "role_id": world.rb["Administrator"].id},
                    headers=h["a_admin"])
    assert r.status_code == 422  # role from another company
    r = client.post("/api/v1/users", json={"username": "evil2", "full_name": "E", "password": "Passw0rd1",
                                           "role_id": world.ra["Salesman"].id, "branch_id": world.branch_b.id}, headers=h["a_admin"])
    assert r.status_code == 422
    assert client.get(f"/api/v1/companies/{world.b.id}", headers=h["a_admin"]).status_code == 404
    assert client.put(f"/api/v1/companies/{world.b.id}", json={"name": "Pwned"}, headers=h["a_admin"]).status_code == 404
    assert [c["id"] for c in client.get("/api/v1/companies", headers=h["a_admin"]).json()] == [world.a.id]


def test_reports_and_dashboard_are_company_scoped(client, world, h):
    new_customer(client, h["a_manager"], name="A only")
    rep = client.get("/api/v1/reports/customers", headers=h["a_manager"]).json()
    assert [r["name"] for r in rep["rows"]] == ["A only"]
    dash = client.get("/api/v1/dashboard", headers=h["b_admin"]).json()
    assert dash["total_customers"] == 1  # only B's customer
    dash_a = client.get("/api/v1/dashboard", headers=h["a_admin"]).json()
    assert dash_a["total_customers"] == 1
