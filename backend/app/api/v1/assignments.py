"""Assignment endpoints live under /customers/{id}/assignments (see customers.py). This module adds the
cross-customer view used by managers: GET /assignments (active assignments, optionally per salesman)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.db.session import get_db
from app.models import Customer, CustomerSalesman
from app.schemas.common import Page, PageParams, paginate
from app.schemas.crm import AssignmentOut
from app.services import customers as svc

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=Page[AssignmentOut])
def list_active_assignments(salesman_id: int | None = None, p: PageParams = Depends(),
                            ctx: CurrentUser = Depends(require_permission("Customer.Assign")), db: Session = Depends(get_db)):
    stmt = select(CustomerSalesman).where(CustomerSalesman.company_id == ctx.company_id, CustomerSalesman.is_active == True)  # noqa: E712
    if salesman_id:
        stmt = stmt.where(CustomerSalesman.salesman_id == salesman_id)
    rows, total = paginate(db, stmt.order_by(CustomerSalesman.assigned_at.desc(), CustomerSalesman.id.desc()), p)
    items = [a for r in rows for a in svc.assignment_history(db, r.customer_id, only_active=True)]
    return Page(items=items, total=total, page=p.page, page_size=p.page_size)
