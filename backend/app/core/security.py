"""Password hashing (Argon2id), JWT creation/validation and a small login rate limiter."""
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.exceptions import TooManyRequests, Unauthorized

_hasher = PasswordHasher()  # Argon2id by default


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, company_id: int, expires_minutes: int | None = None) -> tuple[str, str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes if expires_minutes is not None else s.access_token_minutes)
    jti = uuid.uuid4().hex
    payload = {"sub": str(user_id), "cid": company_id, "jti": jti, "iat": now, "exp": exp}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), jti, exp


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub", "jti"]})
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token has expired")
    except jwt.PyJWTError:
        raise Unauthorized("Invalid token")


class LoginRateLimiter:
    """In-memory sliding window keyed by (ip, username). Use Redis/gateway limits for multi-instance deployments."""

    def __init__(self):
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: int) -> list[float]:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < window]
        self._hits[key] = hits
        return hits

    def check(self, key: str) -> None:
        s = get_settings()
        with self._lock:
            if len(self._prune(key, s.login_window_seconds)) >= s.login_max_attempts:
                raise TooManyRequests("Too many failed login attempts. Try again later.")

    def fail(self, key: str) -> None:
        with self._lock:
            self._hits.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_limiter = LoginRateLimiter()
