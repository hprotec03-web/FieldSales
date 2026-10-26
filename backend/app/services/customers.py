from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import CurrentUser
from app.core.exceptions import Conflict, InvalidRelation
from app.models import Customer, CustomerSalesman, FollowUp, FollowUpOutcome, User, Visit
from app.repositories.scopes import active_assignment, customers_stmt
from app.schemas.crm import ActivityItem, AssigneeOut, AssignmentOut, CustomerOut
from app.utils.time import utcnow


def find_duplicate(db: Session, company_id: int, name: str, mobile: str, exclude_id: int | None = None) -> Customer | None:
    """Configurable rule (settings.duplicate_rule): mobile | name_mobile | name | off. Always company-scoped."""
    rule = get_settings().duplicate_rule
    if rule == "off":
        return None
    stmt = select(Customer).where(Customer.company_id == company_id)
    if rule in ("mobile", "name_mobile"):
        stmt = stmt.where(Customer.mobile == mobile)
    if rule in ("name", "name_mobile"):
        stmt = stmt.where(func.lower(Customer.name) == name.strip().lower())
    if exclude_id:
        stmt = stmt.where(Customer.id != exclude_id)
    return db.scalars(stmt).first()


def _raise_if_duplicate(db, company_id, name, mobile, exclude_id=None):
    dup = find_duplicate(db, company_id, name, mobile, exclude_id)
    if dup:
        raise Conflict("A matching customer already exists", details={"customer_id": dup.id, "rule": get_settings().duplicate_rule})


def create_customer(db: Session, ctx: CurrentUser, data, assign_to_self: bool = False) -> Customer:
    _raise_if_duplicate(db, ctx.company_id, data.name, data.mobile)
    c = Customer(
        company_id=ctx.company_id, created_by_user_id=ctx.id, status="Active",
        name=data.name, mobile=data.mobile, city=data.city,
        country=data.country or get_settings().default_country,
        **data.model_dump(exclude={"name", "mobile", "city", "country", "salesman_id"}),
    )
    db.add(c)
    db.flush()
    if assign_to_self:
        assign_customer(db, ctx, c, ctx.id)
    elif getattr(data, "salesman_id", None):
        ctx.require("Customer.Assign")
        assign_customer(db, ctx, c, data.salesman_id)
    return c


def update_customer(db: Session, ctx: CurrentUser, c: Customer, data) -> Customer:
    fields = data.model_dump(exclude_unset=True)
    for required in ("name", "mobile", "city"):
        if required in fields and not fields[required]:
            raise InvalidRelation(f"{required} cannot be empty")
    if "name" in fields or "mobile" in fields:
        _raise_if_duplicate(db, ctx.company_id, fields.get("name", c.name), fields.get("mobile", c.mobile), exclude_id=c.id)
    for k, v in fields.items():
        if k == "country" and not v:
            v = get_settings().default_country
        setattr(c, k, v)
    c.updated_at = utcnow()
    db.flush()
    return c


def assign_customer(db: Session, ctx: CurrentUser, customer: Customer, salesman_id: int) -> CustomerSalesman:
    salesman = db.scalars(select(User).where(User.id == salesman_id, User.company_id == ctx.company_id)).first()
    if not salesman:
        raise InvalidRelation("Salesman does not exist in your company")
    if salesman.status != "Active":
        raise InvalidRelation("Salesman account is not active")
    if customer.company_id != salesman.company_id:
        raise InvalidRelation("Customer and salesman belong to different companies")
    current = active_assignment(db, customer.id)
    if current and current.salesman_id == salesman_id:
        return current
    if current:
        current.is_active = False
        current.ended_at = utcnow()
        db.flush()  # end the old row BEFORE inserting the new one (filtered unique index)
    new = CustomerSalesman(
        company_id=customer.company_id, customer_id=customer.id, salesman_id=salesman_id,
        assigned_by_user_id=ctx.id, assigned_at=utcnow(), is_active=True,
    )
    db.add(new)
    db.flush()
    return new


def assignee_map(db: Session, customer_ids: list[int]) -> dict[int, AssigneeOut]:
    if not customer_ids:
        return {}
    rows = db.execute(
        select(CustomerSalesman.customer_id, User.id, User.full_name, CustomerSalesman.assigned_at)
        .join(User, User.id == CustomerSalesman.salesman_id)
        .where(CustomerSalesman.customer_id.in_(customer_ids), CustomerSalesman.is_active == True)  # noqa: E712
    ).all()
    return {cid: AssigneeOut(id=uid, full_name=name, assigned_at=at) for cid, uid, name, at in rows}


def to_out(db: Session, customers: list[Customer]) -> list[CustomerOut]:
    amap = assignee_map(db, [c.id for c in customers])
    out = []
    for c in customers:
        o = CustomerOut.model_validate(c)
        o.assigned_salesman = amap.get(c.id)
        out.append(o)
    return out


def list_stmt(ctx: CurrentUser, q=None, status=None, city=None, business_type=None, salesman_id=None, unassigned=None):
    stmt = customers_stmt(ctx)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.name.like(like), Customer.mobile.like(like), Customer.contact_person.like(like), Customer.city.like(like)))
    if status:
        stmt = stmt.where(Customer.status == status)
    if city:
        stmt = stmt.where(Customer.city == city)
    if business_type:
        stmt = stmt.where(Customer.business_type == business_type)
    active_ids = select(CustomerSalesman.customer_id).where(CustomerSalesman.is_active == True)  # noqa: E712
    if salesman_id:
        stmt = stmt.where(Customer.id.in_(active_ids.where(CustomerSalesman.salesman_id == salesman_id)))
    if unassigned:
        stmt = stmt.where(Customer.id.notin_(active_ids))
    return stmt.order_by(Customer.name, Customer.id)


def assignment_history(db: Session, customer_id: int, only_active: bool = False) -> list[AssignmentOut]:
    sal = User.__table__.alias("sal")
    by = User.__table__.alias("by")
    stmt = (
        select(CustomerSalesman, sal.c.full_name, by.c.full_name)
        .join(sal, sal.c.id == CustomerSalesman.salesman_id)
        .join(by, by.c.id == CustomerSalesman.assigned_by_user_id)
        .where(CustomerSalesman.customer_id == customer_id)
        .order_by(CustomerSalesman.assigned_at.desc(), CustomerSalesman.id.desc())
    )
    if only_active:
        stmt = stmt.where(CustomerSalesman.is_active == True)  # noqa: E712
    return [
        AssignmentOut(
            id=a.id, customer_id=a.customer_id, salesman_id=a.salesman_id, salesman_name=sn,
            assigned_by_user_id=a.assigned_by_user_id, assigned_by_name=bn, assigned_at=a.assigned_at,
            ended_at=a.ended_at, is_active=a.is_active,
        )
        for a, sn, bn in db.execute(stmt).all()
    ]


def delete_customer(db: Session, customer: Customer) -> None:
    refs = (db.scalar(select(func.count()).select_from(Visit).where(Visit.customer_id == customer.id)) or 0) + (
        db.scalar(select(func.count()).select_from(FollowUp).where(FollowUp.customer_id == customer.id)) or 0
    )
    if refs:
        raise Conflict("Customer has visits or follow-ups; deactivate it instead of deleting")
    for a in db.scalars(select(CustomerSalesman).where(CustomerSalesman.customer_id == customer.id)).all():
        db.delete(a)
    db.delete(customer)


def activity(db: Session, customer_id: int, limit: int = 100) -> list[ActivityItem]:
    items: list[ActivityItem] = []
    for v, uname in db.execute(
        select(Visit, User.full_name).join(User, User.id == Visit.user_id).where(Visit.customer_id == customer_id)
    ).all():
        items.append(ActivityItem(type="visit", at=v.visit_time, user_id=v.user_id, user_name=uname,
                                  summary=f"Visit: {v.purpose or 'no purpose'}" + (f" ({v.outcome})" if v.outcome else ""), ref_id=v.id))
    for f, uname in db.execute(
        select(FollowUp, User.full_name).join(User, User.id == FollowUp.user_id).where(FollowUp.customer_id == customer_id)
    ).all():
        items.append(ActivityItem(type="follow_up", at=f.created_at, user_id=f.user_id, user_name=uname,
                                  summary=f"Follow-up created: {f.title} ({f.status})", ref_id=f.id))
    for o, uname in db.execute(
        select(FollowUpOutcome, User.full_name)
        .join(User, User.id == FollowUpOutcome.recorded_by_user_id)
        .join(FollowUp, FollowUp.id == FollowUpOutcome.follow_up_id)
        .where(FollowUp.customer_id == customer_id)
    ).all():
        items.append(ActivityItem(type="outcome", at=o.recorded_at, user_id=o.recorded_by_user_id, user_name=uname,
                                  summary=f"Outcome: {o.outcome_text[:200]}", ref_id=o.follow_up_id))
    for a in assignment_history(db, customer_id):
        items.append(ActivityItem(type="assignment", at=a.assigned_at, user_id=a.assigned_by_user_id, user_name=a.assigned_by_name,
                                  summary=f"Assigned to {a.salesman_name}", ref_id=a.id))
    items.sort(key=lambda i: i.at, reverse=True)
    return items[:limit]
