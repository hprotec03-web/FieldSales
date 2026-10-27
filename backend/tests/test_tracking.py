from datetime import timedelta

from tests.test_attendance import DXB, HERE, THERE, _post, check_in, clock  # noqa: F401  (clock is a fixture)


def ping(clock, minutes_ago=0, lat=25.1124, lng=55.1390, acc=10.0, **kw):
    t = clock.now - timedelta(minutes=minutes_ago)
    return {"recorded_at": t.isoformat() + "Z", "latitude": lat, "longitude": lng, "accuracy": acc, **kw}


def send(client, h, pings, status=200):
    return _post(client, h, "/pings", {"pings": pings}, status)


def test_points_only_during_working_time(client, world, h, clock):
    s1 = h["a_sales1"]
    # before check-in: nothing to attach to
    assert send(client, s1, [ping(clock)]) == {"accepted": 0, "ignored": 1, "tracking": False}

    check_in(client, s1)
    clock.advance(minutes=10)
    r = send(client, s1, [ping(clock, lat=25.1200)])
    assert r == {"accepted": 1, "ignored": 0, "tracking": True}
    assert send(client, s1, [ping(clock, lat=25.1200)])["ignored"] == 1  # a retry of the same point is not stored twice

    clock.advance(minutes=10)
    _post(client, s1, "/break/start", {**HERE, "break_type": "Lunch"})
    clock.advance(minutes=10)
    r = send(client, s1, [ping(clock)])  # during the break: ignored, and the phone is told to stop
    assert r == {"accepted": 0, "ignored": 1, "tracking": False}
    _post(client, s1, "/break/end", HERE)
    clock.advance(minutes=10)
    assert send(client, s1, [ping(clock)])["tracking"] is True

    clock.advance(minutes=5)
    _post(client, s1, "/check-out", HERE)
    clock.advance(minutes=10)
    assert send(client, s1, [ping(clock)]) == {"accepted": 0, "ignored": 1, "tracking": False}

    day = client.get("/api/v1/attendance", headers=s1).json()["items"][0]
    assert day["ping_count"] == 2


def test_offline_points_uploaded_late_go_to_the_right_session(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1)
    queued = []
    for _ in range(3):  # phone offline for 30 minutes, keeps collecting
        clock.advance(minutes=10)
        queued.append(ping(clock, lat=25.1124 + len(queued) * 0.01))
    clock.advance(minutes=5)
    _post(client, s1, "/check-out", THERE)
    clock.advance(hours=1)
    r = send(client, s1, queued)  # back online after the day ended: still attached to that day
    assert r["accepted"] == 3 and r["tracking"] is False


def test_distance_gap_last_seen_and_route(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1, loc={"latitude": 25.0, "longitude": 55.0, "accuracy": 5})
    clock.advance(minutes=10)
    send(client, s1, [ping(clock, lat=25.01, lng=55.0)])           # ~1.11 km north
    clock.advance(minutes=10)
    send(client, s1, [ping(clock, lat=25.02, lng=55.0)])           # another ~1.11 km
    clock.advance(minutes=1)
    send(client, s1, [ping(clock, lat=26.5, lng=55.0)])            # ~165 km in 1 minute: GPS jump, not counted
    clock.advance(minutes=1)
    send(client, s1, [ping(clock, lat=25.03, lng=55.0, acc=900)])  # very rough fix: shown, not used for distance
    clock.advance(minutes=48)                                      # no signal for 48 minutes

    team = client.get(f"/api/v1/attendance/team?tz_offset_minutes={DXB}", headers=h["a_manager"]).json()
    s = next(r["session"] for r in team["rows"] if r["user_name"] == "A Sales1")
    assert s["ping_count"] == 4 and abs(s["distance_km"] - 2.22) < 0.05
    assert s["last_seen"]["latitude"] == 25.03 and s["last_seen"]["source"] == "tracking"
    assert s["max_gap_minutes"] == 48

    rt = client.get(f"/api/v1/attendance/{s['id']}/route", headers=h["a_manager"]).json()
    assert [p["kind"] for p in rt["points"]] == ["check_in", "tracking", "tracking", "tracking", "tracking"]
    assert rt["ping_count"] == 4 and rt["distance_km"] == s["distance_km"]
    # route visibility follows attendance visibility
    assert client.get(f"/api/v1/attendance/{s['id']}/route", headers=h["a_sales2"]).status_code == 404
    assert client.get(f"/api/v1/attendance/{s['id']}/route", headers=h["b_admin"]).status_code == 404


def test_validation_and_permissions(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1)
    send(client, s1, [], status=422)
    send(client, s1, [{**ping(clock), "latitude": 123}], status=422)
    # another salesman's points never land in my session
    check_in(client, h["a_sales2"])
    clock.advance(minutes=10)
    send(client, h["a_sales2"], [ping(clock)])
    mine = client.get("/api/v1/attendance", headers=s1).json()["items"][0]
    assert mine["ping_count"] == 0


def test_tracking_report_and_attendance_columns(client, world, h, clock):
    s1 = h["a_sales1"]
    check_in(client, s1, loc={"latitude": 25.0, "longitude": 55.0, "accuracy": 5})
    clock.advance(minutes=10)
    send(client, s1, [ping(clock, lat=25.01, lng=55.0)])
    clock.advance(minutes=10)
    _post(client, s1, "/check-out", {"latitude": 25.02, "longitude": 55.0, "accuracy": 5})

    track = client.get("/api/v1/reports/attendance-track", headers=h["a_manager"]).json()
    assert [r["event"] for r in track["rows"]] == ["Checked in", "Location update", "Checked out"]
    assert track["rows"][0]["km_from_previous"] == 0 and abs(track["rows"][1]["km_from_previous"] - 1.11) < 0.02

    att = client.get("/api/v1/reports/attendance", headers=h["a_manager"]).json()["rows"][0]
    assert abs(att["distance_km"] - 2.22) < 0.05 and att["tracking_points"] == 1 and att["longest_gap"] == "0h 10m"
