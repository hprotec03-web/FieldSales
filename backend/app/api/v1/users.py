from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.core.permissions import ALL_PERMISSIONS
from app.db.session import get_db
from app.models import Permission, Role, User
from app.schemas.auth import PermissionOut, RoleOut, RolePermissionsIn, UserCreate, UserOut, UserUpdate
from app.schemas.common import Page, PageParams, paginate
from app.services import org

router = APIRouter(tags=["users"])


@router.get("/users", response_model=Page[UserOut])
def list_users(
    q: str | None = None, role_id: int | None = None, status: str | None = None,
    scope: str | None = Query(None, description="'assigned' lists only salesmen-type users"),
    p: PageParams = Depends(), ctx: CurrentUser = Depends(require_permission("User.View")), db: Session = Depends(get_db),
):
    stmt = select(User).where(User.company_id == ctx.company_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.like(like), User.username.like(like)))
    if role_id:
        stmt = stmt.where(User.role_id == role_id)
    if status:
        stmt = stmt.where(User.status == status)
    if scope:
        stmt = stmt.where(User.role_id.in_(select(Role.id).where(Role.company_id == ctx.company_id, Role.data_scope == scope)))
    rows, total = paginate(db, stmt.order_by(User.full_name, User.id), p)
    return Page(items=rows, total=total, page=p.page, page_size=p.page_size)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, ctx: CurrentUser = Depends(require_permission("User.Create")), db: Session = Depends(get_db)):
    u = org.create_user(db, ctx, data)
    db.commit()
    return u


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, ctx: CurrentUser = Depends(require_permission("User.View")), db: Session = Depends(get_db)):
    return org.get_user(db, ctx, user_id)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, ctx: CurrentUser = Depends(require_permission("User.Edit")),
                db: Session = Depends(get_db)):
    u = org.update_user(db, ctx, org.get_user(db, ctx, user_id), data)
    db.commit()
    return u


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, ctx: CurrentUser = Depends(require_permission("User.Delete")), db: Session = Depends(get_db)):
    org.delete_user(db, ctx, org.get_user(db, ctx, user_id))
    db.commit()


@router.get("/roles", response_model=list[RoleOut])
def list_roles(ctx: CurrentUser = Depends(require_permission("User.View")), db: Session = Depends(get_db)):
    return db.scalars(select(Role).where(Role.company_id == ctx.company_id).order_by(Role.name)).all()


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(ctx: CurrentUser = Depends(require_permission("User.View")), db: Session = Depends(get_db)):
    return db.scalars(select(Permission).where(Permission.code.in_(ALL_PERMISSIONS)).order_by(Permission.code)).all()


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
def set_role_permissions(role_id: int, data: RolePermissionsIn, ctx: CurrentUser = Depends(require_permission("Company.Edit")),
                         db: Session = Depends(get_db)):
    role = org.set_role_permissions(db, ctx, org.get_role(db, ctx, role_id), data.permission_codes)
    db.commit()
    return role
