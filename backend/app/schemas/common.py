import re
from datetime import date, datetime
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, PlainSerializer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.utils.time import iso_z

T = TypeVar("T")
# Output datetimes are naive UTC in the DB; serialise with a 'Z' so every client parses them correctly.
UTCDateTime = Annotated[datetime, PlainSerializer(iso_z, return_type=str, when_used="json")]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
        self.page, self.page_size = page, page_size


def paginate(db: Session, stmt, p: PageParams):
    """stmt MUST have an ORDER BY (SQL Server requires it for OFFSET/FETCH)."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.limit(p.page_size).offset((p.page - 1) * p.page_size)).unique().all()
    return rows, total


def normalize_mobile(v: str) -> str:
    v = re.sub(r"[\s\-().]", "", v.strip())
    if not re.fullmatch(r"\+?\d{6,15}", v):
        raise ValueError("Enter a valid phone number (6-15 digits, optional leading +)")
    return v


def blank_to_none(v):
    if isinstance(v, str) and not v.strip():
        return None
    return v.strip() if isinstance(v, str) else v


def day_start(d: date | None) -> datetime | None:
    return datetime(d.year, d.month, d.day) if d else None
