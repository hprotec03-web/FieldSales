from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models import Customer, FollowUp, Visit
from tests.conftest import assign, new_customer


def _assigned(client, h, world, salesman="a_sales1"):
    c = new_customer(client, h["a_manager"], name="Visit Target", mobile="+971508888888")
    assign(client, h["a_manager"], c["id"], getattr(world, salesman).id)
    return c


def test_authorized_visit_creation_without_gps(client, world, h):
    c = _assigned(client, h, world)
    r = client.post("/api/v1/visits", json={"customer_id": c["id"], "purpose": "Demo", "outcome": "Interested", "notes": "ok"}, headers=h["a_sales1"])
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["user_id"] == world.a_sales1.id and v["latitude"] is None and v["follow_up_id"] is None
    assert v["visit_time"]  # defaults to now
    assert client.get(f"/api/v1/visits/{v['id']}", headers=h["a_sales1"]).status_code == 200
    assert client.get(f"/api/v1/visits?customer_id={c['id']}", headers=h["a_manager"]).json()["total"] == 1


def test_salesman_cannot_visit_unassigned_customer(client, world, h):
    c = _assigned(client, h, world, "a_sales2")
    assert client.post("/api/v1/visits", json={"customer_id": c["id"]}, headers=h["a_sales1"]).status_code == 404
    assert client.get("/api/v1/visits", headers=h["a_sales1"]).json()["total"] == 0


def test_gps_is_optional_but_must_be_a_valid_pair(client, world, h):
    c = _assigned(client, h, world)
    ok = client.post("/api/v1/visits", json={"customer_id": c["id"], "latitude": 25.2048, "longitude": 55.2708}, headers=h["a_sales1"])
    assert ok.status_code == 201
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "latitude": 25.2}, headers=h["a_sales1"]).status_code == 422
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "latitude": 123, "longitude": 10}, headers=h["a_sales1"]).status_code == 422


def test_must_provide_exactly_one_of_customer_or_new_customer(client, world, h):
    assert client.post("/api/v1/visits", json={"purpose": "x"}, headers=h["a_sales1"]).status_code == 422
    c = _assigned(client, h, world)
    both = {"customer_id": c["id"], "new_customer": {"name": "N", "mobile": "+971509999999", "city": "Dubai"}}
    assert client.post("/api/v1/visits", json=both, headers=h["a_sales1"]).status_code == 422


def test_customer_creation_through_visit_workflow(client, world, h):
    r = client.post("/api/v1/visits", json={"new_customer": {"name": "Walk-in Cafe", "mobile": "+971501010101", "city": "Dubai",
                                                              "business_type": "Restaurant"}, "purpose": "Cold visit"}, headers=h["a_sales1"])
    assert r.status_code == 201, r.text
    cust = client.get(f"/api/v1/customers/{r.json()['customer_id']}", headers=h["a_sales1"]).json()
    assert cust["created_by_user_id"] == world.a_sales1.id
    assert cust["assigned_salesman"]["id"] == world.a_sales1.id
    # ... but this exception does NOT unlock the general customer-management module:
    assert client.post("/api/v1/customers", json={"name": "Direct", "mobile": "+971501010102", "city": "Dubai"}, headers=h["a_sales1"]).status_code == 403
    assert client.put(f"/api/v1/customers/{cust['id']}", json={"name": "Renamed"}, headers=h["a_sales1"]).status_code == 403


def test_duplicate_customer_in_visit_workflow_is_rejected_and_nothing_saved(client, world, h, db):
    new_customer(client, h["a_manager"], name="Existing", mobile="+971501212121")
    r = client.post("/api/v1/visits", json={"new_customer": {"name": "Existing", "mobile": "+971501212121", "city": "Dubai"}}, headers=h["a_sales1"])
    assert r.status_code == 409
    assert db.scalar(select(func.count()).select_from(Visit)) == 0


def test_invalid_branch_ids_are_rejected_not_stored(client, world, h, db):
    c = _assigned(client, h, world)
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "branch_id": 99999}, headers=h["a_sales1"]).status_code == 422
    assert client.post("/api/v1/visits", json={"customer_id": c["id"], "branch_id": world.branch_b.id}, headers=h["a_sales1"]).status_code == 422
    assert db.scalar(select(func.count()).select_from(Visit)) == 0
    ok = client.post("/api/v1/visits", json={"customer_id": c["id"], "branch_id": world.branch_a.id}, headers=h["a_sales1"])
    assert ok.status_code == 201 and ok.json()["branch_name"] == "HQ A"


def test_visit_creates_pending_followup_when_date_given(client, world, h, db):
    c = _assigned(client, h, world)
    due = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0)
    r = client.post("/api/v1/visits", json={"customer_id": c["id"], "follow_up_date": due.isoformat(), "follow_up_notes": "Send quote"},
                    headers=h["a_sales1"])
    assert r.status_code == 201, r.text
    fu = client.get(f"/api/v1/followups/{r.json()['follow_up_id']}", headers=h["a_sales1"]).json()
    assert fu["status"] == "Pending" and fu["title"] == "Follow-up with Visit Target"
    assert fu["notes"] == "Send quote" and fu["customer_id"] == c["id"] and fu["completed_at"] is None
    assert fu["visit_id"] == r.json()["id"]


def test_no_followup_when_fields_empty(client, world, h, db):
    c = _assigned(client, h, world)
    r = client.post("/api/v1/visits", json={"customer_id": c["id"], "follow_up_date": None, "follow_up_notes": ""}, headers=h["a_sales1"])
    assert r.status_code == 201 and r.json()["follow_up_id"] is None
    assert db.scalar(select(func.count()).select_from(FollowUp)) == 0


def test_visit_and_followup_are_one_transaction(client, world, h, db, monkeypatch):
    """If the follow-up step fails, neither the visit nor a newly created customer may remain."""
    from app.services import followups

    def boom(*a, **k):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(followups, "create_followup_record", boom)
    payload = {"new_customer": {"name": "Atomic Co", "mobile": "+971501313131", "city": "Dubai"},
               "follow_up_date": (datetime.utcnow() + timedelta(days=1)).isoformat()}
    r = client.post("/api/v1/visits", json=payload, headers=h["a_sales1"])
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "server_error" and "simulated" not in r.text  # no internal details leaked
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Visit)) == 0
    assert db.scalar(select(func.count()).select_from(FollowUp)) == 0
    assert db.scalars(select(Customer).where(Customer.name == "Atomic Co")).first() is None


def test_visit_filters(client, world, h):
    c = _assigned(client, h, world)
    for days, outcome in ((10, "Interested"), (2, "No Answer")):
        t = (datetime.utcnow() - timedelta(days=days)).isoformat()
        assert client.post("/api/v1/visits", json={"customer_id": c["id"], "visit_time": t, "outcome": outcome}, headers=h["a_sales1"]).status_code == 201
    base = "/api/v1/visits"
    assert client.get(f"{base}?outcome=No Answer", headers=h["a_manager"]).json()["total"] == 1
    assert client.get(f"{base}?salesman_id={world.a_sales1.id}", headers=h["a_manager"]).json()["total"] == 2
    assert client.get(f"{base}?salesman_id={world.a_sales2.id}", headers=h["a_manager"]).json()["total"] == 0
    since = (datetime.utcnow() - timedelta(days=5)).date().isoformat()
    assert client.get(f"{base}?date_from={since}", headers=h["a_manager"]).json()["total"] == 1
