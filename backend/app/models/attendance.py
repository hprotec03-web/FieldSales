"""Salesman attendance: one session per working day (check-in -> breaks -> check-out), each event with GPS location."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, Unicode, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.time import utcnow

BREAK_TYPES = ("Lunch", "Tea", "Prayer", "Personal", "Other")
CHECKOUT_METHODS = ("manual", "logout", "auto")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        # at most one open session per user
        Index("uq_attendance_open_per_user", "user_id", unique=True,
              mssql_where=text("status = 'Open'"), sqlite_where=text("status = 'Open'")),
        Index("ix_attendance_company_date", "company_id", "work_date"),
        Index("ix_attendance_user_date", "user_id", "work_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    work_date: Mapped[date] = mapped_column(Date)  # the salesman's local date at check-in
    tz_offset_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Unicode(20), default="Open")  # Open | Closed

    check_in_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    check_in_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    check_in_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    check_in_accuracy: Mapped[float | None] = mapped_column(Float)
    check_in_address: Mapped[str | None] = mapped_column(Unicode(300))
    check_in_area: Mapped[str | None] = mapped_column(Unicode(150))
    check_in_mocked: Mapped[bool] = mapped_column(Boolean, default=False)
    check_in_note: Mapped[str | None] = mapped_column(Unicode(500))

    check_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    check_out_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_out_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    check_out_accuracy: Mapped[float | None] = mapped_column(Float)
    check_out_address: Mapped[str | None] = mapped_column(Unicode(300))
    check_out_area: Mapped[str | None] = mapped_column(Unicode(150))
    check_out_mocked: Mapped[bool] = mapped_column(Boolean, default=False)
    check_out_method: Mapped[str | None] = mapped_column(Unicode(20))  # manual | logout | auto
    check_out_note: Mapped[str | None] = mapped_column(Unicode(500))

    device_info: Mapped[str | None] = mapped_column(Unicode(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    breaks: Mapped[list["AttendanceBreak"]] = relationship(
        back_populates="attendance", lazy="selectin", order_by="AttendanceBreak.start_at")


class AttendanceBreak(Base):
    __tablename__ = "attendance_breaks"
    __table_args__ = (
        # at most one open break per session
        Index("uq_attendance_break_open", "attendance_id", unique=True,
              mssql_where=text("end_at IS NULL"), sqlite_where=text("end_at IS NULL")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    break_type: Mapped[str] = mapped_column(Unicode(30), default="Other")
    note: Mapped[str | None] = mapped_column(Unicode(500))

    start_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    start_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    start_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    start_accuracy: Mapped[float | None] = mapped_column(Float)
    start_address: Mapped[str | None] = mapped_column(Unicode(300))
    start_area: Mapped[str | None] = mapped_column(Unicode(150))
    start_mocked: Mapped[bool] = mapped_column(Boolean, default=False)

    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    end_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    end_accuracy: Mapped[float | None] = mapped_column(Float)
    end_address: Mapped[str | None] = mapped_column(Unicode(300))
    end_area: Mapped[str | None] = mapped_column(Unicode(150))
    end_mocked: Mapped[bool] = mapped_column(Boolean, default=False)

    attendance: Mapped[Attendance] = relationship(back_populates="breaks")


class LocationPing(Base):
    """Background GPS point sent by the phone every ~10 minutes while the salesman is working (not on a break)."""
    __tablename__ = "location_pings"
    __table_args__ = (
        Index("ix_location_pings_attendance_time", "attendance_id", "recorded_at"),
        UniqueConstraint("user_id", "recorded_at", name="uq_location_ping_user_time"),  # retries never duplicate a point
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime)  # when the phone took the fix (UTC, whole seconds)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    accuracy: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)  # m/s
    is_mocked: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(Unicode(20), default="background")
