"""Attendance: check-in, breaks and check-out, each with a GPS fix.

Rules
* One open session per user (enforced by a filtered unique index too).
* A user can only act on their OWN session; viewing other people's attendance needs Attendance.View
  and a company-wide data scope.
* A session left open past its working day (salesman forgot to check out) is closed automatically
  at the last known activity (check-in, break, tracking point or visit), marked check_out_method = "auto".
* Background tracking: the phone sends a GPS point every ~10 minutes while working. Points before
  check-in, during a break or after check-out are ignored, so nothing is stored outside working time.
"""
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import Conflict
from app.models import Branch, Role, User, Visit
from app.models.attendance import Attendance, AttendanceBreak, LocationPing
from app.schemas.attendance import (AttendanceOut, BreakOut, BreakStart, CheckIn, CheckOut, LastSeen, LocationIn, LocationOut,
                                    PingBatch, PingResult, RouteOut, RoutePoint)
from app.utils.time import utcnow


# ---------- helpers ----------
def _dec(v: float | None) -> Decimal | None:
    return None if v is None else Decimal(str(round(v, 6)))


def local_date(at: datetime, offset_minutes: int) -> date:
    return (at + timedelta(minutes=offset_minutes)).date()


def _open_break(a: Attendance) -> AttendanceBreak | None:
    return next((b for b in a.breaks if b.end_at is None), None)


def current_session(db: Session, ctx: CurrentUser) -> Attendance | None:
    return db.scalars(select(Attendance).where(Attendance.user_id == ctx.id, Attendance.status == "Open")).first()


def is_stale(a: Attendance, now: datetime) -> bool:
    """The session belongs to an earlier working day than the salesman's 'today'."""
    return a.status == "Open" and local_date(now, a.tz_offset_minutes) > a.work_date


def _last_activity(db: Session, a: Attendance) -> datetime:
    times = [a.check_in_at] + [b.start_at for b in a.breaks] + [b.end_at for b in a.breaks if b.end_at]
    day_end = datetime.combine(a.work_date + timedelta(days=1), datetime.min.time()) - timedelta(minutes=a.tz_offset_minutes)
    last_visit = db.scalar(select(func.max(Visit.visit_time)).where(
        Visit.user_id == a.user_id, Visit.visit_time >= a.check_in_at, Visit.visit_time < day_end))
    if last_visit:
        times.append(last_visit)
    last_ping = db.scalar(select(func.max(LocationPing.recorded_at)).where(
        LocationPing.attendance_id == a.id, LocationPing.recorded_at < day_end))
    if last_ping:
        times.append(last_ping)
    return max(times)


def auto_close(db: Session, a: Attendance) -> None:
    at = _last_activity(db, a)
    b = _open_break(a)
    if b:
        b.end_at = max(b.start_at, at)
    a.check_out_at, a.check_out_method, a.status = at, "auto", "Closed"
    a.check_out_note = "Closed automatically: no check-out was recorded"


def close_if_stale(db: Session, a: Attendance | None, now: datetime | None = None) -> Attendance | None:
    """Returns the session if it is still open for today, otherwise closes it and returns None."""
    if a and is_stale(a, now or utcnow()):
        auto_close(db, a)
        db.flush()
        return None
    return a


def _require_open(db: Session, ctx: CurrentUser) -> Attendance:
    a = close_if_stale(db, current_session(db, ctx))
    if not a:
        raise Conflict("You are not checked in. Start your day first.")
    return a


def _loc_fields(prefix: str, loc: LocationIn) -> dict:
    return {
        f"{prefix}_lat": _dec(loc.latitude), f"{prefix}_lng": _dec(loc.longitude), f"{prefix}_accuracy": loc.accuracy,
        f"{prefix}_address": loc.address, f"{prefix}_area": loc.area, f"{prefix}_mocked": loc.is_mocked,
    }


# ---------- actions (own session only) ----------
def check_in(db: Session, ctx: CurrentUser, data: CheckIn) -> Attendance:
    now = utcnow()
    today = local_date(now, data.tz_offset_minutes)
    cur = close_if_stale(db, current_session(db, ctx), now)
    if cur:
        raise Conflict("You are already checked in")
    a = Attendance(company_id=ctx.company_id, user_id=ctx.id, branch_id=ctx.user.branch_id, work_date=today,
                   tz_offset_minutes=data.tz_offset_minutes, status="Open", check_in_at=now,
                   check_in_note=data.note, device_info=data.device_info, **_loc_fields("check_in", data))
    db.add(a)
    try:
        db.flush()
    except IntegrityError:  # a parallel request checked in first
        db.rollback()
        raise Conflict("You are already checked in")
    return a


def start_break(db: Session, ctx: CurrentUser, data: BreakStart) -> Attendance:
    a = _require_open(db, ctx)
    if _open_break(a):
        raise Conflict("You are already on a break")
    b = AttendanceBreak(company_id=ctx.company_id, attendance_id=a.id, user_id=ctx.id, break_type=data.break_type,
                        note=data.note, start_at=utcnow(), **_loc_fields("start", data))
    a.breaks.append(b)
    db.flush()
    return a


def end_break(db: Session, ctx: CurrentUser, data: LocationIn) -> Attendance:
    a = _require_open(db, ctx)
    b = _open_break(a)
    if not b:
        raise Conflict("You are not on a break")
    b.end_at = utcnow()
    for k, v in _loc_fields("end", data).items():
        setattr(b, k, v)
    db.flush()
    return a


def check_out(db: Session, ctx: CurrentUser, data: CheckOut) -> Attendance:
    now = utcnow()
    a = current_session(db, ctx)
    if not a:
        raise Conflict("You are not checked in")
    if is_stale(a, now):  # forgot to check out on an earlier day: close it at the last activity instead of now
        auto_close(db, a)
        db.flush()
        return a
    b = _open_break(a)
    if b:  # checking out ends the running break at the same place
        b.end_at = now
        for k, v in _loc_fields("end", data).items():
            setattr(b, k, v)
    a.check_out_at, a.check_out_method, a.check_out_note, a.status = now, data.method, data.note, "Closed"
    for k, v in _loc_fields("check_out", data).items():
        setattr(a, k, v)
    db.flush()
    return a


# ---------- visibility ----------
def sees_team(ctx: CurrentUser) -> bool:
    return ctx.has("Attendance.View") and not ctx.scoped


def sessions_stmt(ctx: CurrentUser):
    stmt = select(Attendance).where(Attendance.company_id == ctx.company_id)
    if not sees_team(ctx):
        stmt = stmt.where(Attendance.user_id == ctx.id)
    return stmt


def field_staff(db: Session, ctx: CurrentUser) -> list[tuple[int, str, int | None]]:
    """Active users whose role is limited to assigned customers (salesmen)."""
    return list(db.execute(
        select(User.id, User.full_name, User.branch_id).join(Role, Role.id == User.role_id)
        .where(User.company_id == ctx.company_id, User.status == "Active", Role.data_scope == "assigned")
        .order_by(User.full_name)).all())


# ---------- output ----------
def _loc_out(lat, lng, acc, addr, area, mocked) -> LocationOut:
    return LocationOut(latitude=float(lat) if lat is not None else None, longitude=float(lng) if lng is not None else None,
                       accuracy=acc, address=addr, area=area, is_mocked=bool(mocked))


def _secs(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds())


def to_out(db: Session, rows: list[Attendance], now: datetime | None = None, with_track: bool = True) -> list[AttendanceOut]:
    now = now or utcnow()
    if not rows:
        return []
    pings = load_pings(db, [a.id for a in rows]) if with_track else {}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_({a.user_id for a in rows}))).all())
    bids = {a.branch_id for a in rows if a.branch_id}
    branches = dict(db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(bids))).all()) if bids else {}
    out = []
    for a in rows:
        end = a.check_out_at or now
        breaks, break_secs = [], 0.0
        for b in a.breaks:
            s = _secs(b.start_at, b.end_at or end)
            break_secs += s
            breaks.append(BreakOut(
                id=b.id, break_type=b.break_type, note=b.note, start_at=b.start_at, end_at=b.end_at, minutes=int(s // 60),
                start=_loc_out(b.start_lat, b.start_lng, b.start_accuracy, b.start_address, b.start_area, b.start_mocked),
                end=_loc_out(b.end_lat, b.end_lng, b.end_accuracy, b.end_address, b.end_area, b.end_mocked) if b.end_at else None,
            ))
        state = "checked_out" if a.status == "Closed" else ("on_break" if _open_break(a) else "working")
        out.append(AttendanceOut(
            id=a.id, user_id=a.user_id, user_name=names.get(a.user_id, ""), branch_name=branches.get(a.branch_id),
            work_date=a.work_date, status=a.status, state=state,
            check_in_at=a.check_in_at, check_in_note=a.check_in_note,
            check_in=_loc_out(a.check_in_lat, a.check_in_lng, a.check_in_accuracy, a.check_in_address, a.check_in_area, a.check_in_mocked),
            check_out_at=a.check_out_at, check_out_method=a.check_out_method, check_out_note=a.check_out_note,
            check_out=_loc_out(a.check_out_lat, a.check_out_lng, a.check_out_accuracy, a.check_out_address, a.check_out_area,
                               a.check_out_mocked) if a.check_out_at else None,
            device_info=a.device_info, breaks=breaks, break_minutes=int(break_secs // 60),
            worked_minutes=int(max(0.0, _secs(a.check_in_at, end) - break_secs) // 60),
            any_mocked=a.check_in_mocked or a.check_out_mocked or any(b.start_mocked or b.end_mocked for b in a.breaks),
            **(track_stats(a, pings.get(a.id, []), now) if with_track else {}),
        ))
    return out


# ---------- background tracking ----------
PING_SLACK = timedelta(minutes=2)       # clock differences between phone and server
MAX_ACCURACY_FOR_DISTANCE = 100.0       # metres; rougher fixes are shown but not used for distance
MAX_SPEED_KMH = 200.0                   # faster "movement" between two fixes is a GPS jump


def add_pings(db: Session, ctx: CurrentUser, batch: PingBatch) -> PingResult:
    """Store tracking points for MY sessions. Points arrive late when the phone was offline, so each point is matched
    to the session that was running at that time; anything outside working time is ignored."""
    now = utcnow()
    times = [p.recorded_at for p in batch.pings]
    lo, hi = min(times), max(times)
    sessions = list(db.scalars(select(Attendance).where(
        Attendance.user_id == ctx.id, Attendance.check_in_at <= hi + PING_SLACK,
        (Attendance.check_out_at.is_(None)) | (Attendance.check_out_at >= lo - PING_SLACK))).all())
    seen = set(db.scalars(select(LocationPing.recorded_at).where(
        LocationPing.user_id == ctx.id, LocationPing.recorded_at >= lo, LocationPing.recorded_at <= hi)).all())
    accepted = ignored = 0
    for p in sorted(batch.pings, key=lambda x: x.recorded_at):
        t = p.recorded_at
        s = next((s for s in sessions if s.check_in_at - PING_SLACK <= t <= (s.check_out_at or now) + PING_SLACK), None)
        on_break = s is not None and any(b.start_at <= t <= (b.end_at or now) for b in s.breaks)
        if t in seen or t > now + PING_SLACK or s is None or on_break:
            ignored += 1
            continue
        db.add(LocationPing(company_id=ctx.company_id, user_id=ctx.id, attendance_id=s.id, recorded_at=t, received_at=now,
                            lat=_dec(p.latitude), lng=_dec(p.longitude), accuracy=p.accuracy, speed=p.speed,
                            is_mocked=p.is_mocked, source=p.source))
        seen.add(t)
        accepted += 1
    db.flush()
    cur = close_if_stale(db, current_session(db, ctx), now)
    return PingResult(accepted=accepted, ignored=ignored, tracking=bool(cur and not _open_break(cur)))


def load_pings(db: Session, attendance_ids: list[int]) -> dict[int, list[LocationPing]]:
    out: dict[int, list[LocationPing]] = {}
    for i in range(0, len(attendance_ids), 1000):  # stay under database parameter limits
        chunk = attendance_ids[i:i + 1000]
        for p in db.scalars(select(LocationPing).where(LocationPing.attendance_id.in_(chunk))
                            .order_by(LocationPing.attendance_id, LocationPing.recorded_at)).all():
            out.setdefault(p.attendance_id, []).append(p)
    return out


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def route_points(a: Attendance, pings: list[LocationPing]) -> list[RoutePoint]:
    """Attendance events + tracking points, in time order."""
    pts: list[RoutePoint] = []

    def add(at, lat, lng, acc, kind, label):
        if at is not None and lat is not None and lng is not None:
            pts.append(RoutePoint(at=at, latitude=float(lat), longitude=float(lng), accuracy=acc, kind=kind, label=label))

    add(a.check_in_at, a.check_in_lat, a.check_in_lng, a.check_in_accuracy, "check_in", "Checked in")
    for b in a.breaks:
        add(b.start_at, b.start_lat, b.start_lng, b.start_accuracy, "break_start", f"{b.break_type} break started")
        add(b.end_at, b.end_lat, b.end_lng, b.end_accuracy, "break_end", "Back to work")
    for p in pings:
        add(p.recorded_at, p.lat, p.lng, p.accuracy, "tracking", "Location update")
    add(a.check_out_at, a.check_out_lat, a.check_out_lng, a.check_out_accuracy, "check_out", "Checked out")
    order = {"check_in": 0, "break_end": 1, "tracking": 2, "break_start": 3, "check_out": 4}
    pts.sort(key=lambda x: (x.at, order[x.kind]))
    return pts


def _distance_km(points: list[RoutePoint]) -> float:
    good = [p for p in points if p.accuracy is None or p.accuracy <= MAX_ACCURACY_FOR_DISTANCE]
    total = 0.0
    prev = None
    for p in good:
        if prev is not None:
            d = _km(prev.latitude, prev.longitude, p.latitude, p.longitude)
            hours = max((p.at - prev.at).total_seconds() / 3600, 1 / 3600)
            if d / hours > MAX_SPEED_KMH:  # GPS jump: skip this point, keep the previous one as anchor
                continue
            total += d
        prev = p
    return round(total, 2)


def _overlap_seconds(start: datetime, end: datetime, intervals: list[tuple[datetime, datetime]]) -> float:
    return sum(max(0.0, (min(end, e) - max(start, s)).total_seconds()) for s, e in intervals)


def _max_gap_minutes(a: Attendance, points: list[RoutePoint], now: datetime) -> int:
    """Longest working stretch (breaks excluded) between two known positions, up to check-out or now."""
    end = a.check_out_at or now
    breaks = [(b.start_at, b.end_at or end) for b in a.breaks]
    times = sorted({p.at for p in points if a.check_in_at <= p.at <= end} | {a.check_in_at, end})
    gap = 0.0
    for t1, t2 in zip(times, times[1:]):
        gap = max(gap, (t2 - t1).total_seconds() - _overlap_seconds(t1, t2, breaks))
    return int(gap // 60)


def track_stats(a: Attendance, pings: list[LocationPing], now: datetime) -> dict:
    points = route_points(a, pings)
    last = points[-1] if points else None
    return {
        "last_seen": LastSeen(latitude=last.latitude, longitude=last.longitude, accuracy=last.accuracy, at=last.at,
                              source=last.kind) if last else None,
        "ping_count": len(pings),
        "distance_km": _distance_km(points),
        "max_gap_minutes": _max_gap_minutes(a, points, now),
    }


def route(db: Session, a: Attendance, now: datetime | None = None) -> RouteOut:
    now = now or utcnow()
    pings = load_pings(db, [a.id]).get(a.id, [])
    points = route_points(a, pings)
    name = db.scalar(select(User.full_name).where(User.id == a.user_id)) or ""
    return RouteOut(attendance_id=a.id, user_name=name, work_date=a.work_date, points=points,
                    distance_km=_distance_km(points), max_gap_minutes=_max_gap_minutes(a, points, now), ping_count=len(pings))
