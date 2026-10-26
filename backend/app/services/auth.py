from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, Forbidden, Unauthorized
from app.core.security import create_access_token, hash_password, login_limiter, verify_password
from app.models import Company, RevokedToken, User
from app.utils.time import utcnow

_DUMMY_HASH = hash_password("timing-equalizer-password-1")


def authenticate(db: Session, username: str, password: str, limiter_key: str) -> User:
    login_limiter.check(limiter_key)
    user = db.scalars(select(User).where(User.username == username.strip())).first()
    ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        login_limiter.fail(limiter_key)
        raise Unauthorized("Invalid username or password")
    if user.status != "Active":
        raise Forbidden(f"Account is {user.status.lower()}")
    company = db.get(Company, user.company_id)
    if not company or not company.is_active:
        raise Forbidden("Company account is inactive")
    login_limiter.reset(limiter_key)
    return user


def issue_token(user: User):
    return create_access_token(user.id, user.company_id)


def revoke_token(db: Session, jti: str, exp) -> None:
    if not db.get(RevokedToken, jti):
        db.add(RevokedToken(jti=jti, expires_at=exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp))
    # opportunistic cleanup of expired denylist rows
    for row in db.scalars(select(RevokedToken).where(RevokedToken.expires_at < utcnow())).all():
        db.delete(row)


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise Unauthorized("Current password is incorrect")
    if verify_password(new, user.password_hash):
        raise Conflict("New password must differ from the current one")
    user.password_hash = hash_password(new)
