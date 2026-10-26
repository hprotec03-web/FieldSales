"""Dashboards are computed from the database on every request and honour company + assignment visibility."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.models import Customer, CustomerSalesman, FollowUp, FollowUpOutcome, Role, User, Visit
from app.repositories.scopes import customers_stmt, followups_stmt, visits_stmt
from app.services import followups as followup_svc
from app.services import visits as visit_svc
from app.utils.time import utcnow, zulu


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def _today_bounds(offset_minutes: int) -> tuple[datetime, datetime]:
    """'Today' in the client's local day, expressed as UTC bounds (e.g. Dubai = +240)."""
    local_now = utcnow() + timedelta(minutes=offset_minutes)
    start_local = datetime(local_now.year, local_now.month, local_now.day)
    start_utc = start_local - timedelta(minutes=offset_minutes)
    return start_utc, start_utc + timedelta(days=1)


def build(db: Session, ctx: CurrentUser, tz_offset_minutes: int = 0) -> dict:
    return zulu(_build(db, ctx, tz_offset_minutes))


def _build(db: Session, ctx: CurrentUser, tz_offset_minutes: int = 0) -> dict:
    now = utcnow()
    today_start, today_end = _today_bounds(tz_offset_minutes)
    customers = customers_stmt(ctx)
    visits = visits_stmt(ctx)
    followups = followups_stmt(ctx)
    pending = followups.where(FollowUp.status == "Pending")
    overdue = pending.where(FollowUp.due_date < now)
    upcoming = pending.where(FollowUp.due_date >= now).order_by(FollowUp.due_date, FollowUp.id).limit(10)

    kind = "salesman" if ctx.scoped else ("admin" if ctx.has("User.Create") else "manager")
    data: dict = {
        "kind": kind,
        "generated_at": now,
        "pending_followups": _count(db, pending),
        "overdue_followups": _count(db, overdue),
        "total_visits": _count(db, visits),
        "todays_visits": _count(db, visits.where(Visit.visit_time >= today_start, Visit.visit_time < today_end)),
        "upcoming_followups": followup_svc.to_out(db, list(db.scalars(upcoming).unique().all())),
    }

    recent_v = list(db.scalars(visits.order_by(Visit.visit_time.desc(), Visit.id.desc()).limit(10)).all())
    data["recent_visits"] = [v.model_dump() for v in visit_svc.to_out(db, recent_v)]

    if ctx.scoped:
        data["assigned_customers"] = _count(db, customers)
        data["created_by_me_visible"] = _count(db, customers.where(Customer.created_by_user_id == ctx.id))
        recent_o = db.execute(
            select(FollowUpOutcome, FollowUp.title, Customer.name, User.full_name)
            .join(FollowUp, FollowUp.id == FollowUpOutcome.follow_up_id)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .join(User, User.id == FollowUpOutcome.recorded_by_user_id)
            .where(FollowUp.id.in_(followups.with_only_columns(FollowUp.id).order_by(None)))
            .order_by(FollowUpOutcome.recorded_at.desc(), FollowUpOutcome.id.desc()).limit(10)
        ).all()
        data["recent_interactions"] = [
            {"follow_up_id": o.follow_up_id, "follow_up_title": t, "customer_name": cn, "recorded_by_name": un,
             "recorded_at": o.recorded_at, "outcome_text": o.outcome_text}
            for o, t, cn, un in recent_o
        ]
        return data

    # ----- company-level (admin / manager) -----
    data["total_customers"] = _count(db, customers)
    data["active_customers"] = _count(db, customers.where(Customer.status == "Active"))
    salesmen = (
        select(User).join(Role, Role.id == User.role_id)
        .where(User.company_id == ctx.company_id, Role.data_scope == "assigned", User.status == "Active")
    )
    data["total_salesmen"] = _count(db, salesmen)
    active_assign = select(CustomerSalesman.customer_id).where(
        CustomerSalesman.company_id == ctx.company_id, CustomerSalesman.is_active == True)  # noqa: E712
    data["assignment_summary"] = {
        "assigned_customers": _count(db, customers.where(Customer.id.in_(active_assign))),
        "unassigned_customers": _count(db, customers.where(Customer.id.notin_(active_assign))),
    }

    # per-salesman activity summaries (grouped queries, then merged)
    sal_rows = db.execute(salesmen.with_only_columns(User.id, User.full_name).order_by(User.full_name)).all()
    assigned = dict(db.execute(
        select(CustomerSalesman.salesman_id, func.count()).where(
            CustomerSalesman.company_id == ctx.company_id, CustomerSalesman.is_active == True)  # noqa: E712
        .group_by(CustomerSalesman.salesman_id)).all())
    v_total = dict(db.execute(select(Visit.user_id, func.count()).where(Visit.company_id == ctx.company_id).group_by(Visit.user_id)).all())
    v_today = dict(db.execute(
        select(Visit.user_id, func.count()).where(Visit.company_id == ctx.company_id, Visit.visit_time >= today_start,
                                                  Visit.visit_time < today_end).group_by(Visit.user_id)).all())
    fu_base = (
        select(CustomerSalesman.salesman_id, func.count())
        .join(FollowUp, FollowUp.customer_id == CustomerSalesman.customer_id)
        .where(CustomerSalesman.company_id == ctx.company_id, CustomerSalesman.is_active == True,  # noqa: E712
               FollowUp.status == "Pending")
    )
    fu_pending = dict(db.execute(fu_base.group_by(CustomerSalesman.salesman_id)).all())
    fu_overdue = dict(db.execute(fu_base.where(FollowUp.due_date < now).group_by(CustomerSalesman.salesman_id)).all())
    data["salesman_summaries"] = [
        {"salesman_id": sid, "salesman_name": name, "assigned_customers": assigned.get(sid, 0),
         "total_visits": v_total.get(sid, 0), "todays_visits": v_today.get(sid, 0),
         "pending_followups": fu_pending.get(sid, 0), "overdue_followups": fu_overdue.get(sid, 0)}
        for sid, name in sal_rows
    ]

    last_visit = (
        select(Visit.customer_id, func.max(Visit.visit_time).label("last_visit"))
        .where(Visit.company_id == ctx.company_id).group_by(Visit.customer_id).subquery()
    )
    rv = db.execute(
        select(Customer.id, Customer.name, Customer.city, last_visit.c.last_visit)
        .join(last_visit, last_visit.c.customer_id == Customer.id)
        .order_by(last_visit.c.last_visit.desc()).limit(5)
    ).all()
    data["recently_visited_customers"] = [{"id": i, "name": n, "city": c, "last_visit": lv} for i, n, c, lv in rv]
    data["recent_activities"] = data["recent_visits"]
    return data
