from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.context import CurrentUser
from app.core.exceptions import Forbidden
from app.db.session import get_db
from app.repositories.scopes import get_customer, get_visit
from app.schemas.common import Page, PageParams, day_start, paginate
from app.schemas.crm import VisitCreate, VisitOut
from app.services import storage
from app.services import visits as svc
from datetime import timedelta

router = APIRouter(prefix="/visits", tags=["visits"])


@router.get("", response_model=Page[VisitOut])
def list_visits(
    customer_id: int | None = None, salesman_id: int | None = None, date_from: date | None = None,
    date_to: date | None = None, outcome: str | None = None, p: PageParams = Depends(),
    ctx: CurrentUser = Depends(require_permission("Visit.View")), db: Session = Depends(get_db),
):
    end = day_start(date_to + timedelta(days=1)) if date_to else None
    stmt = svc.list_stmt(ctx, customer_id, salesman_id, day_start(date_from), end, outcome)
    rows, total = paginate(db, stmt, p)
    return Page(items=svc.to_out(db, rows), total=total, page=p.page, page_size=p.page_size)


@router.post("", response_model=VisitOut, status_code=201)
def create_visit(data: VisitCreate, ctx: CurrentUser = Depends(require_permission("Visit.Create")), db: Session = Depends(get_db)):
    visit, follow_up = svc.create_visit(db, ctx, data)  # customer + visit + follow-up: ONE transaction
    db.commit()
    return svc.to_out(db, [visit], {visit.id: follow_up.id} if follow_up else {})[0]


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit_detail(visit_id: int, ctx: CurrentUser = Depends(require_permission("Visit.View")), db: Session = Depends(get_db)):
    return svc.to_out(db, [get_visit(db, ctx, visit_id)])[0]


@router.post("/{visit_id}/photo", response_model=VisitOut)
async def upload_visit_photo(visit_id: int, file: UploadFile = File(...), ctx: CurrentUser = Depends(require_permission("Visit.Create")),
                             db: Session = Depends(get_db)):
    v = get_visit(db, ctx, visit_id)
    if v.user_id != ctx.id and not ctx.has("Visit.Edit"):
        raise Forbidden("Only the recording user or a user with Visit.Edit can attach a photo")
    raw = await file.read(get_settings().max_upload_bytes + 1)
    v.photo_url = storage.store_image("visits", raw)
    db.commit()
    return svc.to_out(db, [v])[0]
