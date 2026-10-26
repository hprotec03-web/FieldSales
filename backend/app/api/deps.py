import hmac

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import CurrentUser
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.models import Company, RevokedToken, User

_bearer = HTTPBearer(auto_error=False)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(request: Request, creds=Depends(_bearer), db: Session = Depends(get_db)) -> CurrentUser:
    s = get_settings()
    token = creds.credentials if creds else None
    via_cookie = False
    if not token:
        token = request.cookies.get(s.cookie_name)
        via_cookie = bool(token)
    if not token:
        raise Unauthorized("Not authenticated")
    payload = decode_token(token)

    # CSRF (double submit cookie) is required only when the credential came from a cookie.
    if via_cookie and request.method not in SAFE_METHODS:
        header = request.headers.get("X-CSRF-Token")
        cookie = request.cookies.get(s.csrf_cookie_name)
        if not header or not cookie or not hmac.compare_digest(header, cookie):
            raise Forbidden("CSRF validation failed")

    if db.get(RevokedToken, payload["jti"]):
        raise Unauthorized("Token has been revoked")
    user = db.get(User, int(payload["sub"]))
    if not user or user.company_id != payload.get("cid"):
        raise Unauthorized("Invalid token")
    if user.status != "Active":
        raise Forbidden(f"Account is {user.status.lower()}")
    company = db.get(Company, user.company_id)
    if not company or not company.is_active:
        raise Forbidden("Company account is inactive")
    perms = {p.code for p in user.role.permissions}
    return CurrentUser(user=user, permissions=perms, jti=payload["jti"], token_exp=payload["exp"])


def require_permission(code: str):
    def dep(ctx: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        ctx.require(code)
        return ctx

    return dep
