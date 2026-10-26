from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.attendance import BREAK_TYPES
from app.schemas.common import UTCDateTime, blank_to_none


class LocationIn(BaseModel):
    """A GPS fix taken on the device. Location is required for every attendance event."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=100000)  # metres
    address: str | None = Field(default=None, max_length=300)      # reverse-geocoded on the device, if available
    area: str | None = Field(default=None, max_length=150)         # e.g. "Al Barsha, Dubai"
    is_mocked: bool = False                                        # device reports a fake-GPS provider

    _blank = field_validator("address", "area", mode="before")(blank_to_none)


class CheckIn(LocationIn):
    tz_offset_minutes: int = Field(default=0, ge=-840, le=840)
    note: str | None = Field(default=None, max_length=500)
    device_info: str | None = Field(default=None, max_length=200)

    _blank2 = field_validator("note", "device_info", mode="before")(blank_to_none)


class CheckOut(LocationIn):
    method: str = Field(default="manual", pattern="^(manual|logout)$")
    note: str | None = Field(default=None, max_length=500)

    _blank2 = field_validator("note", mode="before")(blank_to_none)


class BreakStart(LocationIn):
    break_type: str = "Other"
    note: str | None = Field(default=None, max_length=500)

    _blank2 = field_validator("note", mode="before")(blank_to_none)

    @field_validator("break_type")
    @classmethod
    def _t(cls, v):
        if v not in BREAK_TYPES:
            raise ValueError(f"Break type must be one of: {', '.join(BREAK_TYPES)}")
        return v


class LocationOut(BaseModel):
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    address: str | None
    area: str | None
    is_mocked: bool


class BreakOut(BaseModel):
    id: int
    break_type: str
    note: str | None
    start_at: UTCDateTime
    start: LocationOut
    end_at: UTCDateTime | None
    end: LocationOut | None
    minutes: int


class AttendanceOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    branch_name: str | None
    work_date: date
    status: str               # Open | Closed
    state: str                # working | on_break | checked_out
    check_in_at: UTCDateTime
    check_in: LocationOut
    check_in_note: str | None
    check_out_at: UTCDateTime | None
    check_out: LocationOut | None
    check_out_method: str | None
    check_out_note: str | None
    device_info: str | None
    breaks: list[BreakOut]
    break_minutes: int
    worked_minutes: int       # (check-out or now) - check-in - breaks
    any_mocked: bool


class CurrentAttendance(BaseModel):
    session: AttendanceOut | None          # open session (working / on break)
    today_closed: AttendanceOut | None = None  # latest finished session today, when nothing is open
    server_time: UTCDateTime
    break_types: list[str] = list(BREAK_TYPES)


class TeamDayRow(BaseModel):
    user_id: int
    user_name: str
    branch_name: str | None
    session: AttendanceOut | None


class TeamDay(BaseModel):
    date: date
    rows: list[TeamDayRow]
    generated_at: UTCDateTime
