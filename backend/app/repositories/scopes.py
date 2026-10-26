"""Visibility-scoped query builders. EVERY read of customers/visits/follow-ups goes through here so the
company-isolation and assignment-visibility rules cannot be bypassed by calling an endpoint with a raw ID."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import NotFound
from app.models import Customer, CustomerSalesman, FollowUp, Visit


def assigned_customer_ids(company_id: int, salesman_id: int):
    return select(CustomerSalesman.customer_id).where(
        CustomerSalesman.company_id == company_id,
        CustomerSalesman.salesman_id == salesman_id,
        CustomerSalesman.is_active == True,  # noqa: E712
    )


def customers_stmt(ctx: CurrentUser):
    stmt = select(Customer).where(Customer.company_id == ctx.company_id)
    if ctx.scoped:
        stmt = stmt.where(Customer.id.in_(assigned_customer_ids(ctx.company_id, ctx.id)))
    return stmt


def visits_stmt(ctx: CurrentUser):
    stmt = select(Visit).where(Visit.company_id == ctx.company_id)
    if ctx.scoped:
        stmt = stmt.where(Visit.customer_id.in_(assigned_customer_ids(ctx.company_id, ctx.id)))
    return stmt


def followups_stmt(ctx: CurrentUser):
    stmt = select(FollowUp).where(FollowUp.company_id == ctx.company_id)
    if ctx.scoped:
        stmt = stmt.where(FollowUp.customer_id.in_(assigned_customer_ids(ctx.company_id, ctx.id)))
    return stmt


def get_customer(db: Session, ctx: CurrentUser, customer_id: int) -> Customer:
    """Returns 404 for both 'does not exist', 'other company' and 'not visible' so nothing leaks."""
    c = db.scalars(customers_stmt(ctx).where(Customer.id == customer_id)).first()
    if not c:
        raise NotFound("Customer not found")
    return c


def get_visit(db: Session, ctx: CurrentUser, visit_id: int) -> Visit:
    v = db.scalars(visits_stmt(ctx).where(Visit.id == visit_id)).first()
    if not v:
        raise NotFound("Visit not found")
    return v


def get_followup(db: Session, ctx: CurrentUser, followup_id: int) -> FollowUp:
    f = db.scalars(followups_stmt(ctx).where(FollowUp.id == followup_id)).first()
    if not f:
        raise NotFound("Follow-up not found")
    return f


def active_assignment(db: Session, customer_id: int) -> CustomerSalesman | None:
    return db.scalars(
        select(CustomerSalesman).where(
            CustomerSalesman.customer_id == customer_id, CustomerSalesman.is_active == True  # noqa: E712
        )
    ).first()
