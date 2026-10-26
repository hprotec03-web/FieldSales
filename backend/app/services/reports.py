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
