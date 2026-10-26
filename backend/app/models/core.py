from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, UniqueConstraint, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.time import utcnow

USER_STATUSES = ("Active", "Inactive", "Suspended")


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(200), unique=True)
    phone: Mapped[str | None] = mapped_column(Unicode(50))
    email: Mapped[str | None] = mapped_column(Unicode(200))
    address: Mapped[str | None] = mapped_column(Unicode(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_branch_company_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    city: Mapped[str | None] = mapped_column(Unicode(100))
    address: Mapped[str | None] = mapped_column(Unicode(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Unicode(100), unique=True)  # e.g. "Customer.View"


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


class Role(Base):
    """Roles are company-scoped so each company can tune its own permission sets."""
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_role_company_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(100))
    # "company": sees every company record. "assigned": only customers currently assigned to the user.
    data_scope: Mapped[str] = mapped_column(Unicode(20), default="assigned")
    permissions: Mapped[list[Permission]] = relationship(secondary="role_permissions", lazy="selectin")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_user_username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    username: Mapped[str] = mapped_column(Unicode(100))
    full_name: Mapped[str] = mapped_column(Unicode(200))
    email: Mapped[str | None] = mapped_column(Unicode(200))
    mobile: Mapped[str | None] = mapped_column(Unicode(50))
    password_hash: Mapped[str] = mapped_column(Unicode(255))
    status: Mapped[str] = mapped_column(Unicode(20), default="Active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    role: Mapped[Role] = relationship(lazy="joined")


class RevokedToken(Base):
    """Logout denylist for JWT ids; rows can be purged after expires_at."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(Unicode(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
