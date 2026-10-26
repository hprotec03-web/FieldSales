"""Attendance: check-in, breaks and check-out, each with a GPS fix.

Rules
* One open session per user (enforced by a filtered unique index too).
* A user can only act on their OWN session; viewing other people's attendance needs Attendance.View
  and a company-wide data scope.
* A session left open past its working day (salesman forgot to check out) is closed automatically
  at the last known activity (check-in, break, or visit), marked check_out_method = "auto".
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import Conflict
from app.models import Branch, Role, User, Visit
from app.models.attendance import Attendance, AttendanceBreak
from app.schemas.attendance import AttendanceOut, BreakOut, BreakStart, CheckIn, CheckOut, LocationIn, LocationOut
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


def to_out(db: Session, rows: list[Attendance], now: datetime | None = None) -> list[AttendanceOut]:
    now = now or utcnow()
    if not rows:
        return []
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
        ))
    return out
