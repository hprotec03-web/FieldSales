from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Permission, Role
from tests.conftest import assign, new_customer


def _seed_activity(client, h, world):
    c1 = new_customer(client, h["a_manager"], name="Report One", mobile="+971510000001")
    c2 = new_customer(client, h["a_manager"], name="Report Two", mobile="+971510000002")
    assign(client, h["a_manager"], c1["id"], world.a_sales1.id)
    assign(client, h["a_manager"], c2["id"], world.a_sales2.id)
    return c1, c2


def _visit(client, headers, cid, when, **kw):
    r = client.post("/api/v1/visits", json={"customer_id": cid, "visit_time": when.isoformat(), **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_visit_report_is_company_scoped_and_filters_by_date(client, world, h):
    c1, c2 = _seed_activity(client, h, world)
    _visit(client, h["a_sales1"], c1["id"], datetime(2026, 1, 10, 9, 0))
    _visit(client, h["a_sales1"], c1["id"], datetime(2026, 2, 10, 9, 0))
    _visit(client, h["a_sales2"], c2["id"], datetime(2026, 2, 11, 9, 0))
    # another company's visit must never appear
    _visit(client, h["b_sales"], world.b_customer.id, datetime(2026, 2, 10, 9, 0))

    allv = client.get("/api/v1/reports/visits", headers=h["a_manager"]).json()
    assert allv["total"] == 3
    feb = client.get("/api/v1/reports/visits?date_from=2026-02-01&date_to=2026-02-28", headers=h["a_manager"]).json()
    assert feb["total"] == 2
    one_day = client.get("/api/v1/reports/visits?date_from=2026-02-10&date_to=2026-02-10", headers=h["a_manager"]).json()
    assert one_day["total"] == 1  # end date is inclusive
    b = client.get("/api/v1/reports/visits", headers=h["b_admin"]).json()
    assert b["total"] == 1 and b["rows"][0]["customer_name"] == "B Customer"
    assert client.get(f"/api/v1/reports/visits?salesman_id={world.a_sales2.id}", headers=h["a_manager"]).json()["total"] == 1


def test_report_visibility_depends_on_role(client, world, h, db):
    c1, c2 = _seed_activity(client, h, world)
    _visit(client, h["a_sales1"], c1["id"], datetime(2026, 3, 1, 9, 0))
    _visit(client, h["a_sales2"], c2["id"], datetime(2026, 3, 1, 10, 0))
    assert client.get("/api/v1/reports/visits", headers=h["a_sales1"]).status_code == 403   # no Reports.View by default
    # grant Reports.View to the Salesman role: results are still restricted to the salesman's own customers
    perm = db.scalars(select(Permission).where(Permission.code == "Reports.View")).first()
    role = db.get(Role, world.ra["Salesman"].id)
    role.permissions = [*role.permissions, perm]
    db.commit()
    r = client.get("/api/v1/reports/visits", headers=h["a_sales1"]).json()
    assert r["total"] == 1 and r["rows"][0]["customer_name"] == "Report One"
    cust = client.get("/api/v1/reports/customers", headers=h["a_sales1"]).json()
    assert [x["name"] for x in cust["rows"]] == ["Report One"]
    act = client.get("/api/v1/reports/salesman-activity", headers=h["a_sales1"]).json()
    assert [x["salesman"] for x in act["rows"]] == ["A Sales1"]
    # and after reassignment the old salesman's report no longer includes the customer
    assign(client, h["a_manager"], c1["id"], world.a_sales2.id)
    assert client.get("/api/v1/reports/visits", headers=h["a_sales1"]).json()["total"] == 0
    assert client.get(f"/api/v1/reports/customer-activity?customer_id={c1['id']}", headers=h["a_sales1"]).status_code == 404


def test_pending_and_overdue_counts_in_reports_and_dashboard(client, world, h):
    c1, _ = _seed_activity(client, h, world)
    now = datetime.utcnow()
    mk = lambda days: client.post("/api/v1/followups", json={"customer_id": c1["id"], "due_date": (now + timedelta(days=days)).isoformat()}, headers=h["a_manager"]).json()
    overdue1, overdue2, upcoming, done = mk(-3), mk(-1), mk(4), mk(-6)
    client.post(f"/api/v1/followups/{done['id']}/complete", headers=h["a_manager"])
    pending = client.get("/api/v1/reports/followups?status=Pending", headers=h["a_manager"]).json()
    assert pending["total"] == 3
    overdue = client.get("/api/v1/reports/followups?overdue=true", headers=h["a_manager"]).json()
    assert sorted(r["id"] for r in overdue["rows"]) == sorted([overdue1["id"], overdue2["id"]])
    completed = client.get("/api/v1/reports/followups?status=Completed", headers=h["a_manager"]).json()
    assert [r["id"] for r in completed["rows"]] == [done["id"]]
    ranged = client.get(f"/api/v1/reports/followups?date_from={(now - timedelta(days=2)).date()}&date_to={(now + timedelta(days=5)).date()}", headers=h["a_manager"]).json()
    assert ranged["total"] == 2  # overdue2 (-1d) and upcoming (+4d)

    for who, kind in (("a_manager", "manager"), ("a_admin", "admin")):
        d = client.get("/api/v1/dashboard", headers=h[who]).json()
        assert d["kind"] == kind and d["pending_followups"] == 3 and d["overdue_followups"] == 2
        assert [f["id"] for f in d["upcoming_followups"]] == [upcoming["id"]]
    s1 = client.get("/api/v1/dashboard", headers=h["a_sales1"]).json()
    assert s1["kind"] == "salesman" and s1["pending_followups"] == 3 and s1["overdue_followups"] == 2 and s1["assigned_customers"] == 1
    s2 = client.get("/api/v1/dashboard", headers=h["a_sales2"]).json()
    assert s2["pending_followups"] == 0 and s2["overdue_followups"] == 0 and s2["assigned_customers"] == 1


def test_dashboard_numbers_come_from_the_database(client, world, h):
    d0 = client.get("/api/v1/dashboard", headers=h["a_admin"]).json()
    assert (d0["total_customers"], d0["total_visits"], d0["total_salesmen"]) == (0, 0, 2)
    c1, _ = _seed_activity(client, h, world)
    _visit(client, h["a_sales1"], c1["id"], datetime.utcnow())
    d1 = client.get("/api/v1/dashboard", headers=h["a_admin"]).json()
    assert (d1["total_customers"], d1["active_customers"], d1["total_visits"], d1["todays_visits"]) == (2, 2, 1, 1)
    summary = {s["salesman_name"]: s for s in d1["salesman_summaries"]}
    assert summary["A Sales1"]["total_visits"] == 1 and summary["A Sales2"]["total_visits"] == 0
    assert d1["assignment_summary"] == {"assigned_customers": 2, "unassigned_customers": 0}
    assert d1["recently_visited_customers"][0]["name"] == "Report One"


def test_csv_export_and_formula_injection_guard(client, world, h):
    new_customer(client, h["a_manager"], name="=HYPERLINK(\"http://evil\")", mobile="+971510000009")
    r = client.get("/api/v1/reports/customers?format=csv", headers=h["a_manager"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text
    assert client.get("/api/v1/reports/customers?format=csv", headers=h["a_sales1"]).status_code == 403


def test_salesman_activity_and_assignment_reports(client, world, h):
    c1, c2 = _seed_activity(client, h, world)
    _visit(client, h["a_sales1"], c1["id"], datetime.utcnow())
    act = {r["salesman"]: r for r in client.get("/api/v1/reports/salesman-activity", headers=h["a_manager"]).json()["rows"]}
    assert act["A Sales1"]["visits"] == 1 and act["A Sales2"]["visits"] == 0
    assign(client, h["a_manager"], c1["id"], world.a_sales2.id)
    rep = client.get("/api/v1/reports/assignments", headers=h["a_manager"]).json()
    assert rep["total"] == 3 and sum(1 for r in rep["rows"] if r["is_active"] == "No") == 1
    ca = client.get(f"/api/v1/reports/customer-activity?customer_id={c1['id']}", headers=h["a_manager"]).json()
    assert {"visit", "assignment"} <= {r["type"] for r in ca["rows"]}


def test_dashboard_chart_data(client, world, h):
    c1, c2 = _seed_activity(client, h, world)
    now = datetime.utcnow()
    _visit(client, h["a_sales1"], c1["id"], now, outcome="Interested")
    _visit(client, h["a_sales1"], c1["id"], now - timedelta(days=1), outcome="Interested")
    _visit(client, h["a_sales2"], c2["id"], now - timedelta(days=2), outcome="Not Interested")
    _visit(client, h["a_sales2"], c2["id"], now - timedelta(days=40))  # outside both chart windows
    _visit(client, h["b_sales"], world.b_customer.id, now, outcome="Interested")  # other company: never counted
    fu = client.post("/api/v1/followups", json={"customer_id": c1["id"], "due_date": (now + timedelta(days=1)).isoformat()}, headers=h["a_manager"]).json()
    client.post(f"/api/v1/followups/{fu['id']}/complete", headers=h["a_manager"])

    d = client.get("/api/v1/dashboard", headers=h["a_admin"]).json()
    assert len(d["visit_trend"]) == 14 and sum(p["visits"] for p in d["visit_trend"]) == 3
    assert d["visit_trend"][-1] == {"date": now.date().isoformat(), "visits": 1}
    assert d["visit_outcomes"] == [{"outcome": "Interested", "visits": 2}, {"outcome": "Not Interested", "visits": 1}]
    assert (d["completed_followups"], d["cancelled_followups"]) == (1, 0)

    # a salesman only sees chart data for their own customers
    s2 = client.get("/api/v1/dashboard", headers=h["a_sales2"]).json()
    assert sum(p["visits"] for p in s2["visit_trend"]) == 1
    assert s2["visit_outcomes"] == [{"outcome": "Not Interested", "visits": 1}]
    assert s2["completed_followups"] == 0
