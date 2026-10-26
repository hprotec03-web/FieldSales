from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.context import CurrentUser
from app.core.exceptions import Forbidden, NotFound
from app.db.session import get_db
from app.models import Branch
from app.models.attendance import Attendance
from app.schemas.attendance import AttendanceOut, BreakStart, CheckIn, CheckOut, CurrentAttendance, LocationIn, TeamDay, TeamDayRow
from app.schemas.common import Page, PageParams, paginate
from app.services import attendance as svc
from app.utils.time import utcnow

router = APIRouter(prefix="/attendance", tags=["attendance"])
Mark = Depends(require_permission("Attendance.Mark"))


def _require_any(ctx: CurrentUser) -> None:
    if not (ctx.has("Attendance.View") or ctx.has("Attendance.Mark")):
        raise Forbidden("Missing permission: Attendance.View")


def _one(db: Session, a: Attendance) -> AttendanceOut:
    return svc.to_out(db, [a])[0]


# ---------- my day ----------
@router.get("/current", response_model=CurrentAttendance)
def current(tz_offset_minutes: int = Query(0, ge=-840, le=840), ctx: CurrentUser = Mark, db: Session = Depends(get_db)):
    """My open session (null when I still need to check in), plus today's finished session if there is one.
    A session forgotten on an earlier day is closed automatically."""
    now = utcnow()
    a = svc.close_if_stale(db, svc.current_session(db, ctx), now)
    db.commit()
    closed = None
    if not a:
        closed = db.scalars(select(Attendance).where(
            Attendance.user_id == ctx.id, Attendance.status == "Closed",
            Attendance.work_date == svc.local_date(now, tz_offset_minutes)).order_by(Attendance.check_in_at.desc())).first()
    return CurrentAttendance(session=_one(db, a) if a else None, today_closed=_one(db, closed) if closed else None, server_time=now)


@router.post("/check-in", response_model=AttendanceOut, status_code=201)
def check_in(data: CheckIn, ctx: CurrentUser = Mark, db: Session = Depends(get_db)):
    a = svc.check_in(db, ctx, data)
    db.commit()
    return _one(db, a)


@router.post("/break/start", response_model=AttendanceOut)
def break_start(data: BreakStart, ctx: CurrentUser = Mark, db: Session = Depends(get_db)):
    a = svc.start_break(db, ctx, data)
    db.commit()
    return _one(db, a)


@router.post("/break/end", response_model=AttendanceOut)
def break_end(data: LocationIn, ctx: CurrentUser = Mark, db: Session = Depends(get_db)):
    a = svc.end_break(db, ctx, data)
    db.commit()
    return _one(db, a)


@router.post("/check-out", response_model=AttendanceOut)
def check_out(data: CheckOut, ctx: CurrentUser = Mark, db: Session = Depends(get_db)):
    a = svc.check_out(db, ctx, data)
    db.commit()
    return _one(db, a)


# ---------- history / team ----------
@router.get("", response_model=Page[AttendanceOut])
def list_sessions(date_from: date | None = None, date_to: date | None = None, user_id: int | None = None,
                  p: PageParams = Depends(), ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Team members' sessions (Attendance.View, company scope) or, for everyone else, only my own."""
    _require_any(ctx)
    stmt = svc.sessions_stmt(ctx)
    if date_from:
        stmt = stmt.where(Attendance.work_date >= date_from)
    if date_to:
        stmt = stmt.where(Attendance.work_date <= date_to)
    if user_id:
        stmt = stmt.where(Attendance.user_id == user_id)
    rows, total = paginate(db, stmt.order_by(Attendance.work_date.desc(), Attendance.check_in_at.desc()), p)
    return Page(items=svc.to_out(db, rows), total=total, page=p.page, page_size=p.page_size)


@router.get("/team", response_model=TeamDay)
def team_day(day: date | None = Query(None, alias="date"), tz_offset_minutes: int = Query(0, ge=-840, le=840),
             ctx: CurrentUser = Depends(require_permission("Attendance.View")), db: Session = Depends(get_db)):
    """Every salesman for one day: their session, or none (= not checked in)."""
    if not svc.sees_team(ctx):
        raise Forbidden("Team attendance needs a company-wide role")
    now = utcnow()
    day = day or svc.local_date(now, tz_offset_minutes)
    sessions = list(db.scalars(select(Attendance).where(Attendance.company_id == ctx.company_id, Attendance.work_date == day)
                               .order_by(Attendance.check_in_at)).all())
    latest: dict[int, Attendance] = {}
    for a in sessions:  # if someone checked in twice that day, show the latest session
        latest[a.user_id] = a
    outs = {o.user_id: o for o in svc.to_out(db, list(latest.values()), now)}
    branches = dict(db.execute(select(Branch.id, Branch.name).where(Branch.company_id == ctx.company_id)).all())
    staff = svc.field_staff(db, ctx)
    rows = [TeamDayRow(user_id=uid, user_name=name, branch_name=branches.get(bid), session=outs.pop(uid, None))
            for uid, name, bid in staff]
    rows += [TeamDayRow(user_id=o.user_id, user_name=o.user_name, branch_name=o.branch_name, session=o) for o in outs.values()]
    return TeamDay(date=day, rows=rows, generated_at=now)


@router.get("/{attendance_id}", response_model=AttendanceOut)
def get_session(attendance_id: int, ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_any(ctx)
    a = db.scalars(svc.sessions_stmt(ctx).where(Attendance.id == attendance_id)).first()
    if not a:
        raise NotFound("Attendance record not found")
    return _one(db, a)

