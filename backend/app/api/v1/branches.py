from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.core.exceptions import Conflict
from app.db.session import get_db
from app.models import Branch
from app.schemas.auth import BranchIn, BranchOut
from app.services import org

router = APIRouter(prefix="/branches", tags=["branches"])


def _dup(db, ctx, name, exclude_id=None):
    stmt = select(Branch).where(Branch.company_id == ctx.company_id, Branch.name == name)
    if exclude_id:
        stmt = stmt.where(Branch.id != exclude_id)
    if db.scalars(stmt).first():
        raise Conflict("A branch with this name already exists")


@router.get("", response_model=list[BranchOut])
def list_branches(ctx: CurrentUser = Depends(require_permission("Branch.View")), db: Session = Depends(get_db)):
    return db.scalars(select(Branch).where(Branch.company_id == ctx.company_id).order_by(Branch.name)).all()


@router.post("", response_model=BranchOut, status_code=201)
def create_branch(data: BranchIn, ctx: CurrentUser = Depends(require_permission("Branch.Create")), db: Session = Depends(get_db)):
    _dup(db, ctx, data.name)
    b = Branch(company_id=ctx.company_id, **data.model_dump())
    db.add(b)
    db.commit()
    return b


@router.get("/{branch_id}", response_model=BranchOut)
def get_branch(branch_id: int, ctx: CurrentUser = Depends(require_permission("Branch.View")), db: Session = Depends(get_db)):
    return org.get_branch(db, ctx, branch_id)


@router.put("/{branch_id}", response_model=BranchOut)
def update_branch(branch_id: int, data: BranchIn, ctx: CurrentUser = Depends(require_permission("Branch.Edit")),
                  db: Session = Depends(get_db)):
    b = org.get_branch(db, ctx, branch_id)
    _dup(db, ctx, data.name, exclude_id=b.id)
    for k, v in data.model_dump().items():
        setattr(b, k, v)
    db.commit()
    return b


@router.delete("/{branch_id}", status_code=204)
def delete_branch(branch_id: int, ctx: CurrentUser = Depends(require_permission("Branch.Delete")), db: Session = Depends(get_db)):
    org.delete_branch(db, ctx, org.get_branch(db, ctx, branch_id))
    db.commit()
