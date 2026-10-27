"""Report queries (scoped by the same helpers as the rest of the API) and a CSV writer that neutralises
spreadsheet formula injection."""
import csv
import io
from datetime import date, datetime, timedelta

from fastapi import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.models import Customer, CustomerSalesman, FollowUp, FollowUpOutcome, User, Visit
from app.repositories.scopes import customers_stmt, followups_stmt, visits_stmt
from app.schemas.common import day_start
from app.services import customers as customer_svc
from app.services import followups as followup_svc
from app.utils.time import utcnow

MAX_ROWS = 10000


def _bounds(date_from: date | None, date_to: date | None):
    start = day_start(date_from)
    end = day_start(date_to + timedelta(days=1)) if date_to else None  # inclusive end date
    return start, end


def csv_response(columns: list[tuple[str, str]], rows: list[dict], filename: str) -> Response:
    def safe(v):
        if v is None:
            return ""
        if isinstance(v, datetime):
            return v.isoformat(sep=" ", timespec="seconds")
        if not isinstance(v, str):
            return str(v)  # numbers / decimals are written as-is
        return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v  # neutralise formula injection

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow([safe(r.get(key)) for key, _ in columns])
    return Response(
        content="﻿" + buf.getvalue(),  # BOM so Excel opens UTF-8 (Arabic names) correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def customers_report(db: Session, ctx: CurrentUser, status=None, city=None, business_type=None, salesman_id=None):
    stmt = customer_svc.list_stmt(ctx, status=status, city=city, business_type=business_type, salesman_id=salesman_id)
    rows = list(db.scalars(stmt.limit(MAX_ROWS)).all())
    out = []
    for c in customer_svc.to_out(db, rows):
        d = c.model_dump()
        d["salesman"] = c.assigned_salesman.full_name if c.assigned_salesman else ""
        out.append(d)
    cols = [("id", "ID"), ("name", "Name"), ("mobile", "Mobile"), ("business_type", "Business Type"), ("product", "Product"),
            ("contact_person", "Contact Person"), ("city", "City"), ("country", "Country"), ("status", "Status"),
            ("salesman", "Assigned Salesman"), ("created_at", "Created At")]
    return cols, out


def assignments_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, salesman_id=None):
    start, end = _bounds(date_from, date_to)
    sal = User.__table__.alias("sal")
    by = User.__table__.alias("by")
    stmt = (
        select(CustomerSalesman, Customer.name, sal.c.full_name, by.c.full_name)
        .join(Customer, Customer.id == CustomerSalesman.customer_id)
        .join(sal, sal.c.id == CustomerSalesman.salesman_id)
        .join(by, by.c.id == CustomerSalesman.assigned_by_user_id)
        .where(CustomerSalesman.company_id == ctx.company_id)
        .order_by(CustomerSalesman.assigned_at.desc(), CustomerSalesman.id.desc())
    )
    if ctx.scoped:  # a restricted user only sees their own current assignments
        stmt = stmt.where(CustomerSalesman.salesman_id == ctx.id, CustomerSalesman.is_active == True)  # noqa: E712
    if salesman_id:
        stmt = stmt.where(CustomerSalesman.salesman_id == salesman_id)
    if start:
        stmt = stmt.where(CustomerSalesman.assigned_at >= start)
    if end:
        stmt = stmt.where(CustomerSalesman.assigned_at < end)
    rows = [
        {"customer_id": a.customer_id, "customer": cn, "salesman": sn, "assigned_by": bn, "assigned_at": a.assigned_at,
         "ended_at": a.ended_at, "is_active": "Yes" if a.is_active else "No"}
        for a, cn, sn, bn in db.execute(stmt.limit(MAX_ROWS)).all()
    ]
    cols = [("customer_id", "Customer ID"), ("customer", "Customer"), ("salesman", "Salesman"), ("assigned_by", "Assigned By"),
            ("assigned_at", "Assigned At"), ("ended_at", "Ended At"), ("is_active", "Active")]
    return cols, rows


def visits_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None, customer_id=None, outcome=None):
    start, end = _bounds(date_from, date_to)
    stmt = visit_list(ctx, customer_id, user_id, start, end, outcome)
    from app.services import visits as visit_svc
    rows = [v.model_dump() for v in visit_svc.to_out(db, list(db.scalars(stmt.limit(MAX_ROWS)).all()))]
    cols = [("id", "ID"), ("visit_time", "Visit Time"), ("customer_name", "Customer"), ("user_name", "Salesman"),
            ("branch_name", "Branch"), ("purpose", "Purpose"), ("outcome", "Outcome"), ("notes", "Notes"),
            ("latitude", "Latitude"), ("longitude", "Longitude"), ("follow_up_id", "Follow-up ID")]
    return cols, rows


def visit_list(ctx, customer_id, user_id, start, end, outcome):
    from app.services import visits as visit_svc
    return visit_svc.list_stmt(ctx, customer_id, user_id, start, end, outcome)


def followups_report(db: Session, ctx: CurrentUser, status=None, overdue=None, date_from=None, date_to=None,
                     salesman_id=None, customer_id=None):
    start, end = _bounds(date_from, date_to)
    stmt = followup_svc.list_stmt(ctx, status=status, customer_id=customer_id, salesman_id=salesman_id,
                                  due_from=start, due_to=end, overdue=overdue)
    rows = []
    for f in followup_svc.to_out(db, list(db.scalars(stmt.limit(MAX_ROWS)).unique().all())):
        d = f.model_dump()
        d["customer_name"] = f.customer.name if f.customer else ""
        d["salesman"] = f.assigned_salesman.full_name if f.assigned_salesman else ""
        d["overdue"] = "Yes" if f.is_overdue else "No"
        rows.append(d)
    cols = [("id", "ID"), ("title", "Title"), ("customer_name", "Customer"), ("salesman", "Current Salesman"),
            ("created_by_name", "Created By"), ("due_date", "Due Date"), ("status", "Status"), ("overdue", "Overdue"),
            ("completed_at", "Completed At"), ("notes", "Notes")]
    return cols, rows


def salesman_activity_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None):
    start, end = _bounds(date_from, date_to)

    def rng(col, stmt):
        if start:
            stmt = stmt.where(col >= start)
        if end:
            stmt = stmt.where(col < end)
        return stmt

    users = select(User.id, User.full_name).where(User.company_id == ctx.company_id).order_by(User.full_name)
    if ctx.scoped:
        users = users.where(User.id == ctx.id)
    visible_customers = customers_stmt(ctx).with_only_columns(Customer.id).order_by(None)

    visits = dict(db.execute(rng(Visit.visit_time, select(Visit.user_id, func.count()).where(
        Visit.company_id == ctx.company_id, Visit.customer_id.in_(visible_customers)).group_by(Visit.user_id))).all())
    created = dict(db.execute(rng(FollowUp.created_at, select(FollowUp.user_id, func.count()).where(
        FollowUp.company_id == ctx.company_id, FollowUp.customer_id.in_(visible_customers)).group_by(FollowUp.user_id))).all())
    completed = dict(db.execute(rng(FollowUp.completed_at, select(FollowUp.user_id, func.count()).where(
        FollowUp.company_id == ctx.company_id, FollowUp.status == "Completed",
        FollowUp.customer_id.in_(visible_customers)).group_by(FollowUp.user_id))).all())
    outcomes = dict(db.execute(rng(FollowUpOutcome.recorded_at, select(FollowUpOutcome.recorded_by_user_id, func.count())
        .join(FollowUp, FollowUp.id == FollowUpOutcome.follow_up_id)
        .where(FollowUpOutcome.company_id == ctx.company_id, FollowUp.customer_id.in_(visible_customers))
        .group_by(FollowUpOutcome.recorded_by_user_id))).all())
    rows = [
        {"salesman_id": uid, "salesman": name, "visits": visits.get(uid, 0), "follow_ups_created": created.get(uid, 0),
         "follow_ups_completed": completed.get(uid, 0), "outcomes_recorded": outcomes.get(uid, 0)}
        for uid, name in db.execute(users).all()
    ]
    cols = [("salesman", "Salesman"), ("visits", "Visits"), ("follow_ups_created", "Follow-ups Created"),
            ("follow_ups_completed", "Follow-ups Completed"), ("outcomes_recorded", "Outcomes Recorded")]
    return cols, rows


def customer_activity_report(db: Session, ctx: CurrentUser, customer):
    items = customer_svc.activity(db, customer.id, limit=MAX_ROWS)
    rows = [i.model_dump() for i in items]
    cols = [("at", "Date"), ("type", "Type"), ("user_name", "User"), ("summary", "Summary")]
    return cols, rows


# ---------- attendance ----------
def _hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _place(loc) -> str:
    if loc is None or loc.latitude is None:
        return ""
    return loc.area or loc.address or f"{loc.latitude:.5f}, {loc.longitude:.5f}"


def _map(loc) -> str:
    return "" if loc is None or loc.latitude is None else f"https://www.google.com/maps?q={loc.latitude},{loc.longitude}"


def _attendance_sessions(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None):
    from app.models.attendance import Attendance
    from app.services import attendance as att_svc
    stmt = att_svc.sessions_stmt(ctx)
    if date_from:
        stmt = stmt.where(Attendance.work_date >= date_from)
    if date_to:
        stmt = stmt.where(Attendance.work_date <= date_to)
    if user_id:
        stmt = stmt.where(Attendance.user_id == user_id)
    stmt = stmt.order_by(Attendance.work_date.desc(), Attendance.check_in_at)
    return att_svc.to_out(db, list(db.scalars(stmt.limit(MAX_ROWS)).all()))


STATE_LABELS = {"working": "Working", "on_break": "On break", "checked_out": "Checked out"}


def attendance_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None):
    """One row per working day per salesman: in/out times and places, breaks and worked hours."""
    rows = []
    for s in _attendance_sessions(db, ctx, date_from, date_to, user_id):
        rows.append({
            "work_date": s.work_date.isoformat(), "salesman": s.user_name, "branch": s.branch_name,
            "check_in_at": s.check_in_at, "check_in_place": _place(s.check_in), "check_in_map": _map(s.check_in),
            "check_out_at": s.check_out_at, "check_out_place": _place(s.check_out), "check_out_map": _map(s.check_out),
            "check_out_method": s.check_out_method or "", "breaks": len(s.breaks), "break_time": _hm(s.break_minutes),
            "worked_time": _hm(s.worked_minutes), "worked_hours": round(s.worked_minutes / 60, 2),
            "distance_km": s.distance_km, "tracking_points": s.ping_count, "longest_gap": _hm(s.max_gap_minutes),
            "status": STATE_LABELS[s.state], "fake_gps": "Yes" if s.any_mocked else "",
        })
    cols = [("work_date", "Date"), ("salesman", "Salesman"), ("branch", "Branch"),
            ("check_in_at", "Check-in"), ("check_in_place", "Check-in location"), ("check_in_map", "Check-in map"),
            ("check_out_at", "Check-out"), ("check_out_place", "Check-out location"), ("check_out_map", "Check-out map"),
            ("check_out_method", "Check-out by"), ("breaks", "Breaks"), ("break_time", "Break time"),
            ("worked_time", "Working time"), ("worked_hours", "Working hours"), ("distance_km", "Distance (km)"),
            ("tracking_points", "Tracking points"), ("longest_gap", "Longest gap without location"),
            ("status", "Status"), ("fake_gps", "Fake GPS")]
    return cols, rows


def _location_events(sessions):
    for s in sessions:
        yield s, "Check-in", s.check_in_at, s.check_in
        for b in s.breaks:
            yield s, f"Break start ({b.break_type})", b.start_at, b.start
            if b.end_at:
                yield s, f"Break end ({b.break_type})", b.end_at, b.end
        if s.check_out_at:
            yield s, "Check-out (auto)" if s.check_out_method == "auto" else "Check-out", s.check_out_at, s.check_out


def attendance_locations_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None):
    """Every attendance event with its GPS position (check-in, each break start/end, check-out)."""
    rows = []
    for s, event, at, loc in _location_events(_attendance_sessions(db, ctx, date_from, date_to, user_id)):
        has = loc is not None and loc.latitude is not None
        rows.append({
            "work_date": s.work_date.isoformat(), "salesman": s.user_name, "time": at, "event": event,
            "area": (loc.area or "") if has else "", "address": (loc.address or "") if has else "",
            "latitude": loc.latitude if has else None, "longitude": loc.longitude if has else None,
            "accuracy_m": round(loc.accuracy) if has and loc.accuracy is not None else None,
            "fake_gps": "Yes" if has and loc.is_mocked else "", "map": _map(loc),
        })
    rows.sort(key=lambda r: (r["salesman"], r["time"]))
    cols = [("work_date", "Date"), ("salesman", "Salesman"), ("time", "Time"), ("event", "Event"), ("area", "Area"),
            ("address", "Address"), ("latitude", "Latitude"), ("longitude", "Longitude"), ("accuracy_m", "Accuracy (m)"),
            ("fake_gps", "Fake GPS"), ("map", "Map")]
    return cols, rows


def attendance_areas_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None):
    """Location-wise summary: per area and salesman, how many check-ins, breaks and check-outs happened there."""
    groups: dict[tuple[str, str], dict] = {}
    for s, event, at, loc in _location_events(_attendance_sessions(db, ctx, date_from, date_to, user_id)):
        if loc is None or loc.latitude is None:
            continue
        area = loc.area or f"~{loc.latitude:.2f}, {loc.longitude:.2f}"  # ~1 km grid when the device gave no area name
        g = groups.setdefault((area, s.user_name), {
            "area": area, "salesman": s.user_name, "days": set(), "check_ins": 0, "breaks": 0, "check_outs": 0, "events": 0,
            "first_seen": at, "last_seen": at, "map": _map(loc)})
        if event.startswith("Check-in"):
            g["check_ins"] += 1
        elif event.startswith("Break start"):
            g["breaks"] += 1
        elif event.startswith("Check-out"):
            g["check_outs"] += 1
        g["events"] += 1  # every event at this place, including break ends
        g["days"].add(s.work_date)
        g["first_seen"], g["last_seen"] = min(g["first_seen"], at), max(g["last_seen"], at)
    rows = []
    for g in sorted(groups.values(), key=lambda g: (g["area"], g["salesman"])):
        g["days"] = len(g["days"])
        rows.append(g)
    cols = [("area", "Area"), ("salesman", "Salesman"), ("days", "Days"), ("check_ins", "Check-ins"), ("breaks", "Breaks"),
            ("check_outs", "Check-outs"), ("events", "Total events"), ("first_seen", "First seen"), ("last_seen", "Last seen"),
            ("map", "Map")]
    return cols, rows


def attendance_track_report(db: Session, ctx: CurrentUser, date_from=None, date_to=None, user_id=None):
    """Every position of the working day (attendance events + background points every ~10 minutes), in time order,
    with the distance from the previous point."""
    from app.models.attendance import Attendance
    from app.services import attendance as att_svc
    stmt = att_svc.sessions_stmt(ctx)
    if date_from:
        stmt = stmt.where(Attendance.work_date >= date_from)
    if date_to:
        stmt = stmt.where(Attendance.work_date <= date_to)
    if user_id:
        stmt = stmt.where(Attendance.user_id == user_id)
    sessions = list(db.scalars(stmt.order_by(Attendance.work_date.desc(), Attendance.check_in_at).limit(2000)).all())
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_({a.user_id for a in sessions}))).all()) if sessions else {}
    pings = att_svc.load_pings(db, [a.id for a in sessions])
    rows = []
    for a in sessions:
        prev = None
        for p in att_svc.route_points(a, pings.get(a.id, [])):
            step = att_svc._km(prev.latitude, prev.longitude, p.latitude, p.longitude) if prev else 0.0
            rows.append({
                "work_date": a.work_date.isoformat(), "salesman": names.get(a.user_id, ""), "time": p.at, "event": p.label,
                "latitude": p.latitude, "longitude": p.longitude,
                "accuracy_m": round(p.accuracy) if p.accuracy is not None else None,
                "km_from_previous": round(step, 2), "map": f"https://www.google.com/maps?q={p.latitude},{p.longitude}",
            })
            prev = p
            if len(rows) >= MAX_ROWS:
                break
    cols = [("work_date", "Date"), ("salesman", "Salesman"), ("time", "Time"), ("event", "Event"), ("latitude", "Latitude"),
            ("longitude", "Longitude"), ("accuracy_m", "Accuracy (m)"), ("km_from_previous", "Km from previous"), ("map", "Map")]
    return cols, rows
