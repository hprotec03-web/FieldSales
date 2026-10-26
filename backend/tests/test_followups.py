from datetime import datetime, timedelta

from tests.conftest import assign, new_customer


def _fu(client, headers, customer_id, days=1, **kw):
    r = client.post("/api/v1/followups", json={"customer_id": customer_id, "due_date": (datetime.utcnow() + timedelta(days=days)).isoformat(), **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _setup(client, h, world):
    c = new_customer(client, h["a_manager"], name="FU Customer", mobile="+971505050505")
    assign(client, h["a_manager"], c["id"], world.a_sales1.id)
    return c


def test_create_followup_defaults(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    assert f["status"] == "Pending" and f["title"] == "Follow-up with FU Customer" and f["outcomes"] == []
    assert f["user_id"] == world.a_sales1.id and f["assigned_salesman"]["id"] == world.a_sales1.id


def test_branch_id_is_not_accepted_on_followups(client, world, h):
    c = _setup(client, h, world)
    r = client.post("/api/v1/followups", json={"customer_id": c["id"], "due_date": datetime.utcnow().isoformat(), "branch_id": 12345}, headers=h["a_sales1"])
    assert r.status_code == 422


def test_complete_sets_status_and_timestamp(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    before = datetime.utcnow() - timedelta(seconds=2)
    r = client.post(f"/api/v1/followups/{f['id']}/complete", headers=h["a_sales1"])
    assert r.status_code == 200
    done = r.json()
    assert done["status"] == "Completed" and done["completed_at"] is not None
    assert done["completed_at"].endswith("Z")
    assert datetime.fromisoformat(done["completed_at"]).replace(tzinfo=None) >= before
    assert client.get(f"/api/v1/followups/{f['id']}", headers=h["a_sales1"]).json()["status"] == "Completed"


def test_complete_with_final_outcome(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    r = client.post(f"/api/v1/followups/{f['id']}/complete", json={"outcome_text": "Deal signed"}, headers=h["a_sales1"])
    assert r.status_code == 200 and [o["outcome_text"] for o in r.json()["outcomes"]] == ["Deal signed"]


def test_multiple_outcomes_are_appended_and_preserved(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    texts = ["Customer requested product details", "Product details sent", "Customer requested a demonstration"]
    for t in texts:
        r = client.post(f"/api/v1/followups/{f['id']}/outcomes", json={"outcome_text": t}, headers=h["a_sales1"])
        assert r.status_code == 201 and r.json()["recorded_by_user_id"] == world.a_sales1.id
    hist = client.get(f"/api/v1/followups/{f['id']}/outcomes", headers=h["a_sales1"]).json()
    assert [o["outcome_text"] for o in hist] == texts
    assert all(o["recorded_by_name"] and o["recorded_at"] for o in hist)
    # editing the follow-up never touches history
    client.put(f"/api/v1/followups/{f['id']}", json={"title": "Renamed", "notes": "n"}, headers=h["a_sales1"])
    assert len(client.get(f"/api/v1/followups/{f['id']}/outcomes", headers=h["a_sales1"]).json()) == 3
    # there is no API to update or delete an outcome
    assert client.put(f"/api/v1/followups/{f['id']}/outcomes/{hist[0]['id']}", json={"outcome_text": "x"}, headers=h["a_sales1"]).status_code in (404, 405)
    assert client.delete(f"/api/v1/followups/{f['id']}/outcomes/{hist[0]['id']}", headers=h["a_sales1"]).status_code in (404, 405)


def test_empty_outcome_rejected(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    assert client.post(f"/api/v1/followups/{f['id']}/outcomes", json={"outcome_text": "   "}, headers=h["a_sales1"]).status_code == 422


def test_status_transitions(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    s = lambda status: client.post(f"/api/v1/followups/{f['id']}/status", json={"status": status}, headers=h["a_sales1"])
    assert s("Cancelled").status_code == 200
    assert client.post(f"/api/v1/followups/{f['id']}/outcomes", json={"outcome_text": "x"}, headers=h["a_sales1"]).status_code == 409
    assert s("Completed").status_code == 409          # Cancelled -> Completed not allowed
    assert s("Pending").status_code == 200            # reopen
    assert s("Completed").status_code == 200
    assert s("Pending").status_code == 409            # Completed is final
    assert client.put(f"/api/v1/followups/{f['id']}", json={"title": "x"}, headers=h["a_sales1"]).status_code == 409
    assert client.post(f"/api/v1/followups/{f['id']}/status", json={"status": "Bogus"}, headers=h["a_sales1"]).status_code == 422


def test_reassignment_follow_up_visibility_and_attribution(client, world, h):
    c = _setup(client, h, world)
    f = _fu(client, h["a_sales1"], c["id"])
    client.post(f"/api/v1/followups/{f['id']}/outcomes", json={"outcome_text": "Called by sales1"}, headers=h["a_sales1"])
    assign(client, h["a_manager"], c["id"], world.a_sales2.id)
    # previous salesman: no list entry, no detail, no outcomes, no edits
    assert client.get("/api/v1/followups", headers=h["a_sales1"]).json()["total"] == 0
    for method, url, body in (("get", f"/api/v1/followups/{f['id']}", None), ("get", f"/api/v1/followups/{f['id']}/outcomes", None),
                              ("post", f"/api/v1/followups/{f['id']}/outcomes", {"outcome_text": "sneaky"}),
                              ("post", f"/api/v1/followups/{f['id']}/complete", None), ("put", f"/api/v1/followups/{f['id']}", {"title": "x"})):
        r = getattr(client, method)(url, headers=h["a_sales1"], **({"json": body} if body else {}))
        assert r.status_code == 404, (method, url, r.status_code)
    # new salesman sees it, can add outcomes, and history keeps the ORIGINAL author
    assert client.get("/api/v1/followups", headers=h["a_sales2"]).json()["total"] == 1
    client.post(f"/api/v1/followups/{f['id']}/outcomes", json={"outcome_text": "Called by sales2"}, headers=h["a_sales2"])
    detail = client.get(f"/api/v1/followups/{f['id']}", headers=h["a_sales2"]).json()
    assert [(o["outcome_text"], o["recorded_by_user_id"]) for o in detail["outcomes"]] == [
        ("Called by sales1", world.a_sales1.id), ("Called by sales2", world.a_sales2.id)]
    assert detail["user_id"] == world.a_sales1.id                         # original creator preserved
    assert detail["assigned_salesman"]["id"] == world.a_sales2.id          # current responsible salesman


def test_list_filters_overdue_upcoming_and_salesman(client, world, h):
    c = _setup(client, h, world)
    past = _fu(client, h["a_manager"], c["id"], days=-2)
    soon = _fu(client, h["a_manager"], c["id"], days=2)
    done = _fu(client, h["a_manager"], c["id"], days=-5)
    client.post(f"/api/v1/followups/{done['id']}/complete", headers=h["a_manager"])
    ids = lambda q: sorted(x["id"] for x in client.get(f"/api/v1/followups?{q}", headers=h["a_manager"]).json()["items"])
    assert ids("overdue=true") == [past["id"]]
    assert ids("upcoming=true") == [soon["id"]]
    assert ids("status=Completed") == [done["id"]]
    assert ids(f"salesman_id={world.a_sales1.id}") == sorted([past["id"], soon["id"], done["id"]])
    assert ids(f"salesman_id={world.a_sales2.id}") == []
    assert ids(f"customer_id={c['id']}&status=Pending") == sorted([past["id"], soon["id"]])
    overdue_flag = [x for x in client.get("/api/v1/followups?overdue=true", headers=h["a_manager"]).json()["items"]][0]
    assert overdue_flag["is_overdue"] is True
    hist = client.get(f"/api/v1/customers/{c['id']}/followups", headers=h["a_sales1"]).json()
    assert len(hist) == 3
