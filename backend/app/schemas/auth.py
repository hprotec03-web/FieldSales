import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORM, UTCDateTime, blank_to_none, normalize_mobile

USER_STATUSES = ("Active", "Inactive", "Suspended")


def check_password_strength(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters and contain letters and digits")
    return v


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    _v = field_validator("new_password")(check_password_strength)


class RoleBrief(ORM):
    id: int
    name: str
    data_scope: str


class UserOut(ORM):
    id: int
    company_id: int
    branch_id: int | None
    role_id: int
    username: str
    full_name: str
    email: str | None
    mobile: str | None
    status: str
    created_at: UTCDateTime
    role: RoleBrief


class MeOut(UserOut):
    company_name: str = ""
    permissions: list[str] = []


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: MeOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    mobile: str | None = None

    _b = field_validator("email", "mobile", mode="before")(blank_to_none)

    @field_validator("mobile")
    @classmethod
    def _m(cls, v):
        return normalize_mobile(v) if v else v


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._@-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    password: str
    role_id: int
    branch_id: int | None = None
    email: EmailStr | None = None
    mobile: str | None = None

    _b = field_validator("email", "mobile", mode="before")(blank_to_none)
    _p = field_validator("password")(check_password_strength)

    @field_validator("mobile")
    @classmethod
    def _m(cls, v):
        return normalize_mobile(v) if v else v


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role_id: int | None = None
    branch_id: int | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    status: str | None = None
    password: str | None = None  # admin password reset

    _b = field_validator("email", "mobile", mode="before")(blank_to_none)

    @field_validator("mobile")
    @classmethod
    def _m(cls, v):
        return normalize_mobile(v) if v else v

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in USER_STATUSES:
            raise ValueError(f"Status must be one of {USER_STATUSES}")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return check_password_strength(v) if v else v


class PermissionOut(ORM):
    id: int
    code: str


class RoleOut(ORM):
    id: int
    name: str
    data_scope: str
    permissions: list[PermissionOut]


class RolePermissionsIn(BaseModel):
    permission_codes: list[str]


class CompanyOut(ORM):
    id: int
    name: str
    phone: str | None
    email: str | None
    address: str | None
    is_active: bool


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)

    _b = field_validator("email", "phone", "address", mode="before")(blank_to_none)


class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    _b = field_validator("city", "address", mode="before")(blank_to_none)


class BranchOut(ORM):
    id: int
    company_id: int
    name: str
    city: str | None
    address: str | None
    is_active: bool
