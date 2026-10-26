from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.core.exceptions import NotFound
from app.db.session import get_db
from app.models import Company
from app.schemas.auth import CompanyOut, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


def _own(db: Session, ctx: CurrentUser, company_id: int) -> Company:
    if company_id != ctx.company_id:  # never reveal other companies
        raise NotFound("Company not found")
    return db.get(Company, company_id)


@router.get("", response_model=list[CompanyOut])
def list_companies(ctx: CurrentUser = Depends(require_permission("Company.View")), db: Session = Depends(get_db)):
    """A user can only ever see their own company."""
    return [db.get(Company, ctx.company_id)]


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, ctx: CurrentUser = Depends(require_permission("Company.View")), db: Session = Depends(get_db)):
    return _own(db, ctx, company_id)


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, data: CompanyUpdate, ctx: CurrentUser = Depends(require_permission("Company.Edit")),
                   db: Session = Depends(get_db)):
    c = _own(db, ctx, company_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "name" and not v:
            continue
        setattr(c, k, v)
    db.commit()
    return c
