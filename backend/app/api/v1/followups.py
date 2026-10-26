from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.db.session import get_db
from app.repositories.scopes import get_customer, get_followup
from app.schemas.common import Page, PageParams, day_start, paginate
from app.schemas.crm import (CompleteIn, FollowUpCreate, FollowUpDetail, FollowUpOut, FollowUpStatusIn, FollowUpUpdate,
                             OutcomeIn, OutcomeOut)
from app.services import followups as svc

router = APIRouter(prefix="/followups", tags=["followups"])


@router.get("", response_model=Page[FollowUpOut])
def list_followups(
    status: str | None = None, customer_id: int | None = None, salesman_id: int | None = None,
    due_from: date | None = None, due_to: date | None = None, overdue: bool | None = None, upcoming: bool | None = None,
    p: PageParams = Depends(), ctx: CurrentUser = Depends(require_permission("FollowUp.View")), db: Session = Depends(get_db),
):
    end = day_start(due_to + timedelta(days=1)) if due_to else None
    stmt = svc.list_stmt(ctx, status, customer_id, salesman_id, day_start(due_from), end, overdue, upcoming)
    rows, total = paginate(db, stmt, p)
    return Page(items=svc.to_out(db, rows), total=total, page=p.page, page_size=p.page_size)


@router.post("", response_model=FollowUpDetail, status_code=201)
def create_followup(data: FollowUpCreate, ctx: CurrentUser = Depends(require_permission("FollowUp.Create")),
                    db: Session = Depends(get_db)):
    customer = get_customer(db, ctx, data.customer_id)
    f = svc.create_followup_record(db, ctx, customer, data.due_date, data.title, data.notes)
    db.commit()
    return svc.to_detail(db, f)


@router.get("/{followup_id}", response_model=FollowUpDetail)
def get_followup_detail(followup_id: int, ctx: CurrentUser = Depends(require_permission("FollowUp.View")),
                        db: Session = Depends(get_db)):
    return svc.to_detail(db, get_followup(db, ctx, followup_id))


@router.put("/{followup_id}", response_model=FollowUpDetail)
def update_followup(followup_id: int, data: FollowUpUpdate, ctx: CurrentUser = Depends(require_permission("FollowUp.Edit")),
                    db: Session = Depends(get_db)):
    f = svc.update_followup(db, get_followup(db, ctx, followup_id), data.model_dump(exclude_unset=True))
    db.commit()
    return svc.to_detail(db, f)


@router.post("/{followup_id}/status", response_model=FollowUpDetail)
def change_status(followup_id: int, data: FollowUpStatusIn, ctx: CurrentUser = Depends(require_permission("FollowUp.Edit")),
                  db: Session = Depends(get_db)):
    f = svc.change_status(db, ctx, get_followup(db, ctx, followup_id), data.status, data.outcome_text)
    db.commit()
    return svc.to_detail(db, f)


@router.post("/{followup_id}/complete", response_model=FollowUpDetail)
def complete(followup_id: int, data: CompleteIn | None = None, ctx: CurrentUser = Depends(require_permission("FollowUp.Complete")),
             db: Session = Depends(get_db)):
    f = svc.change_status(db, ctx, get_followup(db, ctx, followup_id), "Completed", data.outcome_text if data else None)
    db.commit()
    return svc.to_detail(db, f)


@router.get("/{followup_id}/outcomes", response_model=list[OutcomeOut])
def list_outcomes(followup_id: int, ctx: CurrentUser = Depends(require_permission("FollowUp.View")), db: Session = Depends(get_db)):
    return svc.outcomes_for(db, get_followup(db, ctx, followup_id).id)


@router.post("/{followup_id}/outcomes", response_model=OutcomeOut, status_code=201)
def add_outcome(followup_id: int, data: OutcomeIn, ctx: CurrentUser = Depends(require_permission("FollowUp.Edit")),
                db: Session = Depends(get_db)):
    f = get_followup(db, ctx, followup_id)
    o = svc.add_outcome(db, ctx, f, data.outcome_text)
    db.commit()
    return next(x for x in svc.outcomes_for(db, f.id) if x.id == o.id)
