from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import InvalidRelation
from app.models import Branch, Customer, FollowUp, User, Visit
from app.repositories.scopes import get_customer, visits_stmt
from app.schemas.crm import VisitCreate, VisitOut
from app.services import customers as customer_svc
from app.services import followups as followup_svc
from app.services.org import check_branch
from app.utils.time import utcnow


def create_visit(db: Session, ctx: CurrentUser, data: VisitCreate) -> tuple[Visit, FollowUp | None]:
    """Creates (optionally) a customer, the visit and (optionally) a follow-up WITHOUT committing.
    The caller commits once, so any failure rolls back everything (no orphan customer/visit)."""
    check_branch(db, ctx, data.branch_id)

    if data.new_customer is not None:
        # Visit workflow exception: only Visit.Create is needed; no Customer.Create / module access granted.
        customer = customer_svc.create_customer(db, ctx, data.new_customer, assign_to_self=ctx.scoped)
    else:
        customer = get_customer(db, ctx, data.customer_id)  # 404 if other company / not currently visible
    if customer.status != "Active":
        raise InvalidRelation("Cannot record a visit for an inactive customer")

    visit = Visit(
        company_id=ctx.company_id, customer_id=customer.id, user_id=ctx.id, branch_id=data.branch_id,
        visit_time=data.visit_time or utcnow(), latitude=data.latitude, longitude=data.longitude,
        purpose=data.purpose, notes=data.notes, outcome=data.outcome,
    )
    db.add(visit)
    db.flush()

    follow_up = None
    if data.follow_up_date is not None:
        ctx.require("FollowUp.Create")
        follow_up = followup_svc.create_followup_record(
            db, ctx, customer, data.follow_up_date, notes=data.follow_up_notes, visit_id=visit.id
        )
    return visit, follow_up


def to_out(db: Session, visits: list[Visit], follow_ups: dict[int, int] | None = None) -> list[VisitOut]:
    if not visits:
        return []
    cust = dict(db.execute(select(Customer.id, Customer.name).where(Customer.id.in_({v.customer_id for v in visits}))).all())
    users = dict(db.execute(select(User.id, User.full_name).where(User.id.in_({v.user_id for v in visits}))).all())
    bids = {v.branch_id for v in visits if v.branch_id}
    branches = dict(db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(bids))).all()) if bids else {}
    if follow_ups is None:
        follow_ups = dict(db.execute(select(FollowUp.visit_id, FollowUp.id).where(FollowUp.visit_id.in_([v.id for v in visits]))).all())
    out = []
    for v in visits:
        o = VisitOut.model_validate(v)
        o.customer_name, o.user_name = cust.get(v.customer_id), users.get(v.user_id)
        o.branch_name = branches.get(v.branch_id)
        o.follow_up_id = follow_ups.get(v.id)
        out.append(o)
    return out


def list_stmt(ctx: CurrentUser, customer_id=None, user_id=None, date_from=None, date_to=None, outcome=None):
    stmt = visits_stmt(ctx)
    if customer_id:
        stmt = stmt.where(Visit.customer_id == customer_id)
    if user_id:
        stmt = stmt.where(Visit.user_id == user_id)
    if date_from:
        stmt = stmt.where(Visit.visit_time >= date_from)
    if date_to:
        stmt = stmt.where(Visit.visit_time < date_to)
    if outcome:
        stmt = stmt.where(Visit.outcome == outcome)
    return stmt.order_by(Visit.visit_time.desc(), Visit.id.desc())
