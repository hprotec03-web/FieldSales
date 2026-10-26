from datetime import datetime, timedelta

import pytest

DXB = 240  # Dubai, UTC+4
HERE = {"latitude": 25.1124, "longitude": 55.1390, "accuracy": 12.5, "area": "Al Barsha, Dubai", "address": "Al Barsha 1, Dubai"}
THERE = {"latitude": 25.2048, "longitude": 55.2708, "accuracy": 8, "area": "Downtown, Dubai"}


@pytest.fixture
def clock(monkeypatch):
    """Controllable 'now' (naive UTC) for the attendance service and API."""
    state = {"now": datetime(2026, 10, 27, 5, 0)}  # 09:00 in Dubai

    def now():
        return state["now"]

    monkeypatch.setattr("app.services.attendance.utcnow", now)
    monkeypatch.setattr("app.api.v1.attendance.utcnow", now)

    class Clock:
        def advance(self, **kw):
            state["now"] += timedelta(**kw)

        @property
        def now(self):
            return state["now"]
    return Clock()


def _post(client, h, path, body=None, status=200):
    r = client.post(f"/api/v1/attendance{path}", json=body or {}, headers=h)
    assert r.status_code == status, r.text
    return r.json()


def check_in(client, h, loc=HERE, status=201, **kw):
    return _post(client, h, "/check-in", {**loc, "tz_offset_minutes": DXB, "device_info": "Android 14 · Pixel 7", **kw}, status)


def test_full_day_with_breaks_and_working_hours(client, world, h, clock):
    s1 = h["a_sales1"]
    assert client.get("/api/v1/attendance/current", headers=s1).json()["session"] is None

    a = check_in(client, s1)
    assert a["state"] == "working" and a["work_date"] == "2026-10-27" and a["check_in"]["area"] == "Al Barsha, Dubai"
    assert a["check_in"]["accuracy"] == 12.5 and a["device_info"] == "Android 14 · Pixel 7"
    check_in(client, s1, status=409)  # only one open session

    clock.advance(hours=3)
    _post(client, s1, "/break/end", HERE, status=409)  # not on a break
    b = _post(client, s1, "/break/start", {**THERE, "break_type": "Lunch"})
    assert b["state"] == "on_break" and b["breaks"][0]["start"]["area"] == "Downtown, Dubai"
    _post(client, s1, "/break/start", {**THERE, "break_type": "Tea"}, status=409)  # one break at a time

    clock.advance(minutes=45)
    b = _post(client, s1, "/break/end", THERE)
    assert b["state"] == "working" and b["breaks"][0]["minutes"] == 45 and b["break_minutes"] == 45

    clock.advance(hours=5, minutes=15)
    out = _post(client, s1, "/check-out", {**HERE, "method": "logout"})
    assert out["status"] == "Closed" and out["state"] == "checked_out" and out["check_out_method"] == "logout"
    assert out["worked_minutes"] == 9 * 60 - 45 and out["break_minutes"] == 45  # 9h on site minus a 45 min break
    cur = client.get(f"/api/v1/attendance/current?tz_offset_minutes={DXB}", headers=s1).json()
    assert cur["session"] is None and cur["today_closed"]["worked_minutes"] == 9 * 60 - 45
    _post(client, s1, "/check-out", HERE, status=409)


def test_check_out_during_break_ends_the_break(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1)
    clock.advance(hours=1)
    _post(client, s1, "/break/start", {**HERE, "break_type": "Prayer"})
    clock.advance(minutes=20)
    out = _post(client, s1, "/check-out", THERE)
    assert out["breaks"][0]["end"]["area"] == "Downtown, Dubai" and out["breaks"][0]["minutes"] == 20
    assert out["worked_minutes"] == 60


def test_location_is_required_and_validated(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1, loc={}, status=422)
    check_in(client, s1, loc={"latitude": 91, "longitude": 10}, status=422)
    check_in(client, s1)
    _post(client, s1, "/break/start", {**HERE, "break_type": "Holiday"}, status=422)


def test_fake_gps_is_flagged(client, world, h, clock):
    a = check_in(client, h["a_sales1"], loc={**HERE, "is_mocked": True})
    assert a["check_in"]["is_mocked"] is True and a["any_mocked"] is True


def test_forgotten_check_out_is_closed_automatically_next_day(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1)
    clock.advance(hours=2)
    _post(client, s1, "/break/start", {**HERE, "break_type": "Tea"})
    clock.advance(hours=22)  # next morning in Dubai, nothing recorded since
    assert client.get("/api/v1/attendance/current", headers=s1).json()["session"] is None
    old = client.get("/api/v1/attendance", headers=s1).json()["items"][0]
    assert old["status"] == "Closed" and old["check_out_method"] == "auto"
    assert old["worked_minutes"] == 120  # closed at the last known activity (the break start), not 24h later
    new = check_in(client, s1)
    assert new["work_date"] == "2026-10-28"


def test_visibility_and_company_isolation(client, world, h, clock):
    a1 = check_in(client, h["a_sales1"])
    check_in(client, h["b_sales"])
    # a salesman sees only their own records
    assert client.get(f"/api/v1/attendance/{a1['id']}", headers=h["a_sales2"]).status_code == 404
    assert client.get("/api/v1/attendance", headers=h["a_sales2"]).json()["total"] == 0
    assert client.get("/api/v1/attendance/team", headers=h["a_sales1"]).status_code == 403
    # managers see the whole company, never another company
    assert client.get(f"/api/v1/attendance/{a1['id']}", headers=h["a_manager"]).status_code == 200
    assert client.get(f"/api/v1/attendance/{a1['id']}", headers=h["b_admin"]).status_code == 404
    assert client.get("/api/v1/attendance", headers=h["a_manager"]).json()["total"] == 1

    team = client.get(f"/api/v1/attendance/team?tz_offset_minutes={DXB}", headers=h["a_manager"]).json()
    assert team["date"] == "2026-10-27"
    by_name = {r["user_name"]: r for r in team["rows"]}
    assert by_name["A Sales1"]["session"]["state"] == "working"
    assert by_name["A Sales2"]["session"] is None  # not checked in yet
    assert "B Sales" not in by_name


def test_attendance_reports(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1)
    clock.advance(hours=4)
    _post(client, s1, "/break/start", {**THERE, "break_type": "Lunch"})
    clock.advance(minutes=30)
    _post(client, s1, "/break/end", THERE)
    clock.advance(hours=4)
    _post(client, s1, "/check-out", HERE)

    rep = client.get("/api/v1/reports/attendance?date_from=2026-10-27&date_to=2026-10-27", headers=h["a_manager"]).json()
    row = rep["rows"][0]
    assert rep["total"] == 1 and row["salesman"] == "A Sales1" and row["worked_time"] == "8h 00m" and row["worked_hours"] == 8.0
    assert row["break_time"] == "0h 30m" and row["check_in_place"] == "Al Barsha, Dubai" and "google.com/maps" in row["check_in_map"]

    loc = client.get("/api/v1/reports/attendance-locations", headers=h["a_manager"]).json()
    assert [r["event"] for r in loc["rows"]] == ["Check-in", "Break start (Lunch)", "Break end (Lunch)", "Check-out"]

    areas = {r["area"]: r for r in client.get("/api/v1/reports/attendance-areas", headers=h["a_manager"]).json()["rows"]}
    assert areas["Al Barsha, Dubai"]["check_ins"] == 1 and areas["Al Barsha, Dubai"]["check_outs"] == 1
    assert areas["Downtown, Dubai"]["breaks"] == 1 and areas["Downtown, Dubai"]["events"] == 2

    csv = client.get("/api/v1/reports/attendance?format=csv", headers=h["a_manager"])
    assert csv.status_code == 200 and "Working hours" in csv.text
    assert client.get("/api/v1/reports/attendance", headers=h["b_admin"]).json()["total"] == 0  # other company
