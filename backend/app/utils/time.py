from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (SQL Server DATETIME2 has no tz). All stored timestamps are UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(v):
    """Accept aware datetimes from clients (e.g. mobile '...Z') and store naive UTC."""
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


def iso_z(d: datetime) -> str:
    """Naive UTC datetime -> ISO-8601 with 'Z' so browsers/phones do not misread it as local time."""
    return d.isoformat() + "Z" if d.tzinfo is None else d.isoformat()


def zulu(obj):
    """Recursively convert datetimes (and pydantic models) in a response structure to Z-suffixed strings."""
    from pydantic import BaseModel
    if isinstance(obj, datetime):
        return iso_z(obj)
    if isinstance(obj, BaseModel):
        return zulu(obj.model_dump())
    if isinstance(obj, dict):
        return {k: zulu(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [zulu(v) for v in obj]
    return obj
