from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.context import CurrentUser
from app.core.exceptions import Forbidden
from app.core.permissions import BUSINESS_TYPES
from app.db.session import get_db
from app.models import FollowUp
from app.repositories.scopes import followups_stmt, get_customer
from app.schemas.common import Page, PageParams, paginate
from app.schemas.crm import (ActivityItem, AssignmentIn, AssignmentOut, CustomerCreate, CustomerOut, CustomerStatusIn,
                             CustomerUpdate, FollowUpOut)
from app.services import customers as svc
from app.services import followups as followup_svc
from app.services import storage

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/options")
def options(ctx: CurrentUser = Depends(get_current_user)):
    """Controlled dropdown values for business type / product."""
    return {"business_types": BUSINESS_TYPES, "products": BUSINESS_TYPES}


@router.get("", response_model=Page[CustomerOut])
def list_customers(
    q: str | None = None, status: str | None = None, city: str | None = None, business_type: str | None = None,
    salesman_id: int | None = None, unassigned: bool | None = None, p: PageParams = Depends(),
    ctx: CurrentUser = Depends(require_permission("Customer.View")), db: Session = Depends(get_db),
):
    rows, total = paginate(db, svc.list_stmt(ctx, q, status, city, business_type, salesman_id, unassigned), p)
    return Page(items=svc.to_out(db, rows), total=total, page=p.page, page_size=p.page_size)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(data: CustomerCreate, ctx: CurrentUser = Depends(require_permission("Customer.Create")),
                    db: Session = Depends(get_db)):
    c = svc.create_customer(db, ctx, data)
    db.commit()
    return svc.to_out(db, [c])[0]


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer_detail(customer_id: int, ctx: CurrentUser = Depends(require_permission("Customer.View")),
                        db: Session = Depends(get_db)):
    return svc.to_out(db, [get_customer(db, ctx, customer_id)])[0]


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, data: CustomerUpdate, ctx: CurrentUser = Depends(require_permission("Customer.Edit")),
                    db: Session = Depends(get_db)):
    c = svc.update_customer(db, ctx, get_customer(db, ctx, customer_id), data)
    db.commit()
    return svc.to_out(db, [c])[0]


@router.patch("/{customer_id}/status", response_model=CustomerOut)
def set_status(customer_id: int, data: CustomerStatusIn, ctx: CurrentUser = Depends(require_permission("Customer.Edit")),
               db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    c.status = data.status
    db.commit()
    return svc.to_out(db, [c])[0]


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, ctx: CurrentUser = Depends(require_permission("Customer.Delete")),
                    db: Session = Depends(get_db)):
    svc.delete_customer(db, get_customer(db, ctx, customer_id))
    db.commit()


@router.post("/{customer_id}/photo", response_model=CustomerOut)
async def upload_photo(customer_id: int, file: UploadFile = File(...), ctx: CurrentUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    # Customer.Edit, or a salesman (Visit.Create) adding a photo to a customer currently assigned to them.
    if not (ctx.has("Customer.Edit") or (ctx.scoped and ctx.has("Visit.Create"))):
        raise Forbidden("Missing permission: Customer.Edit")
    c = get_customer(db, ctx, customer_id)
    from app.core.config import get_settings
    raw = await file.read(get_settings().max_upload_bytes + 1)
    c.business_photo_url = storage.store_image("customers", raw)
    db.commit()
    return svc.to_out(db, [c])[0]


@router.post("/{customer_id}/assignments", response_model=AssignmentOut, status_code=201)
def assign(customer_id: int, data: AssignmentIn, ctx: CurrentUser = Depends(require_permission("Customer.Assign")),
           db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    svc.assign_customer(db, ctx, c, data.salesman_id)
    db.commit()
    return svc.assignment_history(db, c.id, only_active=True)[0]


@router.get("/{customer_id}/assignments", response_model=list[AssignmentOut])
def assignments(customer_id: int, ctx: CurrentUser = Depends(require_permission("Customer.View")), db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    # Restricted (assigned-scope) users only see the current assignment, not the transfer history.
    return svc.assignment_history(db, c.id, only_active=ctx.scoped)


@router.get("/{customer_id}/activity", response_model=list[ActivityItem])
def customer_activity(customer_id: int, ctx: CurrentUser = Depends(require_permission("Customer.View")),
                      db: Session = Depends(get_db)):
    return svc.activity(db, get_customer(db, ctx, customer_id).id)


@router.get("/{customer_id}/followups", response_model=list[FollowUpOut])
def customer_followups(customer_id: int, ctx: CurrentUser = Depends(require_permission("FollowUp.View")),
                       db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    rows = db.scalars(followups_stmt(ctx).where(FollowUp.customer_id == c.id).order_by(FollowUp.due_date.desc(), FollowUp.id.desc())).unique().all()
    return followup_svc.to_out(db, list(rows))
