from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import Conflict, InvalidRelation
from app.core.permissions import FOLLOWUP_TRANSITIONS
from app.models import Customer, CustomerSalesman, FollowUp, FollowUpOutcome, User
from app.repositories.scopes import followups_stmt
from app.schemas.crm import CustomerBrief, FollowUpDetail, FollowUpOut, OutcomeOut
from app.services.customers import assignee_map
from app.utils.time import utcnow


def default_title(customer: Customer) -> str:
    return f"Follow-up with {customer.name}"


def create_followup_record(db: Session, ctx: CurrentUser, customer: Customer, due_date: datetime,
                           title: str | None = None, notes: str | None = None, visit_id: int | None = None) -> FollowUp:
    """No commit here: callers own the transaction (the Visit workflow saves visit + follow-up atomically)."""
    if customer.company_id != ctx.company_id:
        raise InvalidRelation("Customer belongs to a different company")
    f = FollowUp(
        company_id=ctx.company_id, customer_id=customer.id, user_id=ctx.id, visit_id=visit_id,
        title=title or default_title(customer), notes=notes, due_date=due_date, status="Pending",
    )
    db.add(f)
    db.flush()
    return f


def add_outcome(db: Session, ctx: CurrentUser, f: FollowUp, text: str) -> FollowUpOutcome:
    if f.status != "Pending":
        raise Conflict(f"Cannot add outcomes to a {f.status.lower()} follow-up")
    o = FollowUpOutcome(company_id=f.company_id, follow_up_id=f.id, outcome_text=text,
                        recorded_by_user_id=ctx.id, recorded_at=utcnow())
    db.add(o)
    db.flush()
    return o


def change_status(db: Session, ctx: CurrentUser, f: FollowUp, new_status: str, outcome_text: str | None = None) -> FollowUp:
    if new_status == f.status:
        raise Conflict(f"Follow-up is already {f.status}")
    if new_status not in FOLLOWUP_TRANSITIONS.get(f.status, set()):
        raise Conflict(f"Transition {f.status} -> {new_status} is not allowed")
    ctx.require("FollowUp.Complete" if new_status == "Completed" else "FollowUp.Edit")
    if outcome_text:
        add_outcome(db, ctx, f, outcome_text)  # recorded while still Pending, attributed to the acting user
    f.status = new_status
    f.completed_at = utcnow() if new_status == "Completed" else None
    f.updated_at = utcnow()
    db.flush()
    return f


def update_followup(db: Session, f: FollowUp, fields: dict) -> FollowUp:
    if f.status != "Pending":
        raise Conflict(f"A {f.status.lower()} follow-up cannot be edited")
    for k, v in fields.items():
        if k in ("title", "due_date") and v is None:
            raise InvalidRelation(f"{k} cannot be empty")
        setattr(f, k, v)
    f.updated_at = utcnow()
    db.flush()
    return f


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all())


def to_out(db: Session, followups: list[FollowUp]) -> list[FollowUpOut]:
    amap = assignee_map(db, list({f.customer_id for f in followups}))
    names = _names(db, {f.user_id for f in followups})
    now = utcnow()
    out = []
    for f in followups:
        o = FollowUpOut.model_validate(f)
        o.created_by_name = names.get(f.user_id)
        o.is_overdue = f.status == "Pending" and f.due_date < now
        o.customer = CustomerBrief.model_validate(f.customer)
        o.assigned_salesman = amap.get(f.customer_id)
        out.append(o)
    return out


def outcomes_for(db: Session, follow_up_id: int) -> list[OutcomeOut]:
    rows = db.execute(
        select(FollowUpOutcome, User.full_name)
        .join(User, User.id == FollowUpOutcome.recorded_by_user_id)
        .where(FollowUpOutcome.follow_up_id == follow_up_id)
        .order_by(FollowUpOutcome.recorded_at, FollowUpOutcome.id)
    ).all()
    result = []
    for o, name in rows:
        item = OutcomeOut.model_validate(o)
        item.recorded_by_name = name  # always the person who actually recorded it
        result.append(item)
    return result


def to_detail(db: Session, f: FollowUp) -> FollowUpDetail:
    base = to_out(db, [f])[0]
    return FollowUpDetail(**base.model_dump(), outcomes=outcomes_for(db, f.id))


def list_stmt(ctx: CurrentUser, status=None, customer_id=None, salesman_id=None, due_from=None, due_to=None,
              overdue=None, upcoming=None):
    stmt = followups_stmt(ctx)
    now = utcnow()
    if status:
        stmt = stmt.where(FollowUp.status == status)
    if customer_id:
        stmt = stmt.where(FollowUp.customer_id == customer_id)
    if salesman_id:
        stmt = stmt.where(FollowUp.customer_id.in_(
            select(CustomerSalesman.customer_id).where(
                CustomerSalesman.salesman_id == salesman_id, CustomerSalesman.is_active == True)))  # noqa: E712
    if due_from:
        stmt = stmt.where(FollowUp.due_date >= due_from)
    if due_to:
        stmt = stmt.where(FollowUp.due_date < due_to)
    if overdue:
        stmt = stmt.where(FollowUp.status == "Pending", FollowUp.due_date < now)
    if upcoming:
        stmt = stmt.where(FollowUp.status == "Pending", FollowUp.due_date >= now)
    return stmt.order_by(FollowUp.due_date, FollowUp.id)
