import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.context import CurrentUser
from app.db.session import get_db
from app.models import Company
from app.schemas.auth import ChangePasswordIn, LoginIn, LoginOut, MeOut, ProfileUpdate
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(db: Session, ctx: CurrentUser) -> MeOut:
    company = db.get(Company, ctx.company_id)
    m = MeOut.model_validate(ctx.user)
    m.company_name = company.name if company else ""
    m.permissions = sorted(ctx.permissions)
    return m


@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    key = f"{request.client.host if request.client else 'unknown'}:{data.username.strip().lower()}"
    user = auth_svc.authenticate(db, data.username, data.password, key)
    token, _jti, exp = auth_svc.issue_token(user)
    max_age = s.access_token_minutes * 60
    response.set_cookie(s.cookie_name, token, max_age=max_age, httponly=True, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")
    response.set_cookie(s.csrf_cookie_name, secrets.token_urlsafe(32), max_age=max_age, httponly=False,
                        secure=s.cookie_secure, samesite=s.cookie_samesite, path="/")
    ctx = CurrentUser(user=user, permissions={p.code for p in user.role.permissions})
    return LoginOut(access_token=token, expires_in=max_age, user=_me(db, ctx))


@router.post("/logout", status_code=204)
def logout(response: Response, ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    s = get_settings()
    exp = datetime.fromtimestamp(ctx.token_exp, tz=timezone.utc) if isinstance(ctx.token_exp, (int, float)) else ctx.token_exp
    auth_svc.revoke_token(db, ctx.jti, exp)
    db.commit()
    response.delete_cookie(s.cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.get("/me", response_model=MeOut)
def me(ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _me(db, ctx)


@router.put("/me", response_model=MeOut)
def update_me(data: ProfileUpdate, ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "full_name" and not v:
            continue
        setattr(ctx.user, k, v)
    db.commit()
    return _me(db, ctx)


@router.post("/change-password", status_code=204)
def change_password(data: ChangePasswordIn, ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_svc.change_password(db, ctx.user, data.current_password, data.new_password)
    db.commit()
