from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.time import utcnow


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_company_mobile", "company_id", "mobile"),
        Index("ix_customers_company_name", "company_id", "name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    mobile: Mapped[str] = mapped_column(Unicode(30))
    business_type: Mapped[str | None] = mapped_column(Unicode(100))
    product: Mapped[str | None] = mapped_column(Unicode(100))
    contact_person: Mapped[str | None] = mapped_column(Unicode(200))
    contact_person_mobile: Mapped[str | None] = mapped_column(Unicode(30))
    address: Mapped[str | None] = mapped_column(Unicode(500))
    city: Mapped[str] = mapped_column(Unicode(100))
    country: Mapped[str] = mapped_column(Unicode(100), default="United Arab Emirates")
    email: Mapped[str | None] = mapped_column(Unicode(200))
    location_url: Mapped[str | None] = mapped_column(Unicode(500))
    business_photo_url: Mapped[str | None] = mapped_column(Unicode(500))
    notes: Mapped[str | None] = mapped_column(UnicodeText)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Unicode(20), default="Active")  # Active | Inactive
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CustomerSalesman(Base):
    """Assignment history. Exactly one row per customer may have is_active = 1 (filtered unique index)."""
    __tablename__ = "customer_salesmen"
    __table_args__ = (
        Index(
            "uq_customer_active_assignment", "customer_id", unique=True,
            mssql_where=text("is_active = 1"), sqlite_where=text("is_active = 1"),
        ),
        Index("ix_assignment_salesman_active", "salesman_id", "is_active"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    salesman_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (Index("ix_visits_company_time", "company_id", "visit_time"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # who recorded it
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    visit_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    purpose: Mapped[str | None] = mapped_column(Unicode(300))
    notes: Mapped[str | None] = mapped_column(UnicodeText)
    outcome: Mapped[str | None] = mapped_column(Unicode(100))
    photo_url: Mapped[str | None] = mapped_column(Unicode(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (Index("ix_followups_company_status_due", "company_id", "status", "due_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # original creator; NOT the current owner
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visits.id"))
    title: Mapped[str] = mapped_column(Unicode(300))
    notes: Mapped[str | None] = mapped_column(UnicodeText)
    due_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(Unicode(20), default="Pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(lazy="joined")


class FollowUpOutcome(Base):
    """Append-only interaction history. Rows are never updated or deleted by the application."""
    __tablename__ = "follow_up_outcomes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    follow_up_id: Mapped[int] = mapped_column(ForeignKey("follow_ups.id"), index=True)
    outcome_text: Mapped[str] = mapped_column(UnicodeText)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    attachment_url: Mapped[str | None] = mapped_column(Unicode(500))
