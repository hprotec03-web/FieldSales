"""Company, branch, user and role management. All lookups are company-scoped."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentUser
from app.core.exceptions import Conflict, Forbidden, InvalidRelation, NotFound
from app.core.permissions import ALL_PERMISSIONS, DEFAULT_ROLES
from app.core.security import hash_password
from app.models import Branch, Company, CustomerSalesman, Permission, Role, User, Visit


# ---------- seed helpers (also used by seed script and tests) ----------
def ensure_permissions(db: Session) -> dict[str, Permission]:
    existing = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code in ALL_PERMISSIONS:
        if code not in existing:
            p = Permission(code=code)
            db.add(p)
            existing[code] = p
    db.flush()
    return existing


def create_company_with_roles(db: Session, name: str, **extra) -> tuple[Company, dict[str, Role]]:
    perms = ensure_permissions(db)
    company = Company(name=name, **extra)
    db.add(company)
    db.flush()
    roles = {}
    for role_name, cfg in DEFAULT_ROLES.items():
        r = Role(company_id=company.id, name=role_name, data_scope=cfg["data_scope"])
        r.permissions = [perms[c] for c in cfg["permissions"]]
        db.add(r)
        roles[role_name] = r
    db.flush()
    return company, roles


# ---------- companies / branches ----------
def get_branch(db: Session, ctx: CurrentUser, branch_id: int) -> Branch:
    b = db.scalars(select(Branch).where(Branch.id == branch_id, Branch.company_id == ctx.company_id)).first()
    if not b:
        raise NotFound("Branch not found")
    return b


def check_branch(db: Session, ctx: CurrentUser, branch_id: int | None) -> Branch | None:
    if branch_id is None:
        return None
    b = db.scalars(select(Branch).where(Branch.id == branch_id, Branch.company_id == ctx.company_id)).first()
    if not b:
        raise InvalidRelation("Branch does not exist in your company")
    return b


def delete_branch(db: Session, ctx: CurrentUser, branch: Branch) -> None:
    used = db.scalar(select(func.count()).select_from(Visit).where(Visit.branch_id == branch.id)) or 0
    used += db.scalar(select(func.count()).select_from(User).where(User.branch_id == branch.id)) or 0
    if used:
        raise Conflict("Branch is referenced by visits or users; deactivate it instead")
    db.delete(branch)


# ---------- users ----------
def get_user(db: Session, ctx: CurrentUser, user_id: int) -> User:
    u = db.scalars(select(User).where(User.id == user_id, User.company_id == ctx.company_id)).first()
    if not u:
        raise NotFound("User not found")
    return u


def get_role(db: Session, ctx: CurrentUser, role_id: int) -> Role:
    r = db.scalars(select(Role).where(Role.id == role_id, Role.company_id == ctx.company_id)).first()
    if not r:
        raise InvalidRelation("Role does not exist in your company")
    return r


def create_user(db: Session, ctx: CurrentUser, data) -> User:
    get_role(db, ctx, data.role_id)
    check_branch(db, ctx, data.branch_id)
    if db.scalars(select(User).where(User.username == data.username)).first():
        raise Conflict("Username is already taken")
    u = User(
        company_id=ctx.company_id, role_id=data.role_id, branch_id=data.branch_id, username=data.username,
        full_name=data.full_name.strip(), email=data.email, mobile=data.mobile,
        password_hash=hash_password(data.password), status="Active",
    )
    db.add(u)
    db.flush()
    db.refresh(u)
    return u


def update_user(db: Session, ctx: CurrentUser, user: User, data) -> User:
    fields = data.model_dump(exclude_unset=True)
    is_self = user.id == ctx.id
    if "role_id" in fields and fields["role_id"] is not None:
        if is_self and fields["role_id"] != user.role_id:
            raise Forbidden("You cannot change your own role")
        get_role(db, ctx, fields["role_id"])
        user.role_id = fields["role_id"]
    if "branch_id" in fields:
        check_branch(db, ctx, fields["branch_id"])
        user.branch_id = fields["branch_id"]
    if "status" in fields and fields["status"] is not None:
        if is_self and fields["status"] != "Active":
            raise Forbidden("You cannot deactivate or suspend your own account")
        if fields["status"] != "Active":
            _ensure_no_active_assignments(db, user)
        user.status = fields["status"]
    for k in ("full_name", "email", "mobile"):
        if k in fields:
            setattr(user, k, fields[k])
    if fields.get("password"):
        user.password_hash = hash_password(fields["password"])
    db.flush()
    db.refresh(user)
    return user


def _ensure_no_active_assignments(db: Session, user: User) -> None:
    n = db.scalar(
        select(func.count()).select_from(CustomerSalesman).where(
            CustomerSalesman.salesman_id == user.id, CustomerSalesman.is_active == True  # noqa: E712
        )
    )
    if n:
        raise Conflict(f"User still has {n} assigned customer(s); reassign them first")


def delete_user(db: Session, ctx: CurrentUser, user: User) -> None:
    """Users are referenced by historical records, so 'delete' deactivates the account."""
    if user.id == ctx.id:
        raise Forbidden("You cannot delete your own account")
    _ensure_no_active_assignments(db, user)
    user.status = "Inactive"


# ---------- roles ----------
def set_role_permissions(db: Session, ctx: CurrentUser, role: Role, codes: list[str]) -> Role:
    if role.name == "Administrator":
        raise Forbidden("The Administrator role's permissions cannot be changed")
    unknown = set(codes) - set(ALL_PERMISSIONS)
    if unknown:
        raise InvalidRelation(f"Unknown permissions: {', '.join(sorted(unknown))}")
    perms = {p.code: p for p in db.scalars(select(Permission)).all()}
    role.permissions = [perms[c] for c in sorted(set(codes))]
    db.flush()
    return role
