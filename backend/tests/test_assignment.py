from datetime import datetime, timedelta

from tests.conftest import assign, new_customer


def _setup(client, h, world):
    c = new_customer(client, h["a_manager"], name="Customer X")
    assign(client, h["a_manager"], c["id"], world.a_sales1.id)
    return c


def test_manager_assigns_and_salesman_gains_access(client, world, h):
    c = _setup(client, h, world)
    r = client.get(f"/api/v1/customers/{c['id']}", headers=h["a_sales1"])
    assert r.status_code == 200 and r.json()["assigned_salesman"]["id"] == world.a_sales1.id
    assert [x["id"] for x in client.get("/api/v1/customers", headers=h["a_sales1"]).json()["items"]] == [c["id"]]
    assert client.get("/api/v1/customers", headers=h["a_sales2"]).json()["total"] == 0
    assert client.get(f"/api/v1/customers/{c['id']}", headers=h["a_sales2"]).status_code == 404


def test_reassignment_moves_visibility_and_keeps_history(client, world, h):
    c = _setup(client, h, world)
    assign(client, h["a_manager"], c["id"], world.a_sales2.id)
    # previous salesman loses access everywhere, even by calling the API directly with the customer id
    assert client.get(f"/api/v1/customers/{c['id']}", headers=h["a_sales1"]).status_code == 404
    assert client.get("/api/v1/customers", headers=h["a_sales1"]).json()["total"] == 0
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "purpose": "x"}, headers=h["a_sales1"]).status_code == 404
    assert client.post("/api/v1/followups", json={"customer_id": c["id"], "due_date": datetime.utcnow().isoformat()},
                       headers=h["a_sales1"]).status_code == 404
    # new salesman gains access
    assert client.get(f"/api/v1/customers/{c['id']}", headers=h["a_sales2"]).status_code == 200
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "purpose": "x"}, headers=h["a_sales2"]).status_code == 201
    # history: two rows, exactly one active; managers see all, salesmen only the current one
    hist = client.get(f"/api/v1/customers/{c['id']}/assignments", headers=h["a_manager"]).json()
    assert len(hist) == 2 and sum(1 for a in hist if a["is_active"]) == 1
    assert [a for a in hist if a["is_active"]][0]["salesman_id"] == world.a_sales2.id
    assert [a for a in hist if not a["is_active"]][0]["ended_at"] is not None
    assert len(client.get(f"/api/v1/customers/{c['id']}/assignments", headers=h["a_sales2"]).json()) == 1


def test_creator_does_not_keep_access_after_transfer(client, world, h):
    """Salesman A creates X via the visit workflow, then the manager transfers X to B: A must lose X."""
    r = client.post("/api/v1/visits", json={"new_customer": {"name": "Created By A", "mobile": "+971503333333", "city": "Dubai"}},
                    headers=h["a_sales1"])
    assert r.status_code == 201
    cid = r.json()["customer_id"]
    assert client.get(f"/api/v1/customers/{cid}", headers=h["a_sales1"]).status_code == 200
    assign(client, h["a_manager"], cid, world.a_sales2.id)
    assert client.get(f"/api/v1/customers/{cid}", headers=h["a_sales1"]).status_code == 404
    assert client.get(f"/api/v1/customers/{cid}", headers=h["a_sales2"]).status_code == 200
    assert client.get(f"/api/v1/customers/{cid}", headers=h["a_manager"]).json()["created_by_user_id"] == world.a_sales1.id


def test_reassigning_to_same_salesman_is_idempotent(client, world, h):
    c = _setup(client, h, world)
    assign(client, h["a_manager"], c["id"], world.a_sales1.id)
    assert len(client.get(f"/api/v1/customers/{c['id']}/assignments", headers=h["a_manager"]).json()) == 1


def test_unauthorized_users_cannot_change_assignments(client, world, h):
    c = _setup(client, h, world)
    r = client.post(f"/api/v1/customers/{c['id']}/assignments", json={"salesman_id": world.a_sales2.id}, headers=h["a_sales1"])
    assert r.status_code == 403
    assert client.get(f"/api/v1/customers/{c['id']}", headers=h["a_sales1"]).status_code == 200  # unchanged


def test_cannot_assign_to_inactive_or_unknown_user(client, world, h, db):
    c = new_customer(client, h["a_manager"])
    world.a_sales2.status = "Inactive"
    db.commit()
    assert client.post(f"/api/v1/customers/{c['id']}/assignments", json={"salesman_id": world.a_sales2.id}, headers=h["a_manager"]).status_code == 422
    assert client.post(f"/api/v1/customers/{c['id']}/assignments", json={"salesman_id": 99999}, headers=h["a_manager"]).status_code == 422


def test_cannot_deactivate_user_who_still_has_customers(client, world, h):
    _setup(client, h, world)
    r = client.put(f"/api/v1/users/{world.a_sales1.id}", json={"status": "Inactive"}, headers=h["a_admin"])
    assert r.status_code == 409


def test_duplicate_customer_rule_is_configurable(client, world, h, monkeypatch):
    from app.core.config import get_settings
    new_customer(client, h["a_manager"], name="Dup", mobile="+971504444444")
    dup = client.post("/api/v1/customers", json={"name": "Different Name", "mobile": "+971504444444", "city": "Dubai"}, headers=h["a_manager"])
    assert dup.status_code == 409 and "customer_id" in dup.json()["error"]["details"]
    monkeypatch.setattr(get_settings(), "duplicate_rule", "name_mobile")
    ok = client.post("/api/v1/customers", json={"name": "Different Name", "mobile": "+971504444444", "city": "Dubai"}, headers=h["a_manager"])
    assert ok.status_code == 201
    monkeypatch.setattr(get_settings(), "duplicate_rule", "off")
    assert client.post("/api/v1/customers", json={"name": "Dup", "mobile": "+971504444444", "city": "Dubai"}, headers=h["a_manager"]).status_code == 201
    # another company may reuse the same number
    monkeypatch.setattr(get_settings(), "duplicate_rule", "mobile")
    assert client.post("/api/v1/customers", json={"name": "B Dup", "mobile": "+971504444444", "city": "Dubai"}, headers=h["b_admin"]).status_code == 201


def test_customer_validation_and_search(client, world, h):
    bad = client.post("/api/v1/customers", json={"name": "", "mobile": "abc", "city": ""}, headers=h["a_manager"])
    assert bad.status_code == 422
    assert {d["field"] for d in bad.json()["error"]["details"]} >= {"name", "mobile", "city"}
    bad_type = client.post("/api/v1/customers", json={"name": "T", "mobile": "+971505555555", "city": "X", "business_type": "Spaceships"}, headers=h["a_manager"])
    assert bad_type.status_code == 422
    c = new_customer(client, h["a_manager"], name="Searchable Gym", mobile="+971506666666", business_type="Gym")
    assert c["country"] == "United Arab Emirates"
    new_customer(client, h["a_manager"], name="Other", mobile="+971507777777")
    r = client.get("/api/v1/customers?q=Searchable", headers=h["a_manager"]).json()
    assert r["total"] == 1
    assert client.get("/api/v1/customers?business_type=Gym&page_size=1", headers=h["a_manager"]).json()["total"] == 1
    assert client.get("/api/v1/customers?unassigned=true", headers=h["a_manager"]).json()["total"] == 2
