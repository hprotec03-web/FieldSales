from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.permissions import BUSINESS_TYPES
from app.schemas.common import ORM, UTCDateTime, blank_to_none, normalize_mobile
from app.utils.time import to_naive_utc

VISIT_OUTCOMES = ["Interested", "Not Interested", "Needs Follow-up", "Demo Scheduled", "Deal Closed", "No Answer", "Other"]
CUSTOMER_STATUSES = ("Active", "Inactive")
FOLLOWUP_STATUSES = ("Pending", "Completed", "Cancelled")


def _choice(v, allowed, label):
    if v is not None and v not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
    return v


# ---------- Customers ----------
class CustomerBase(BaseModel):
    business_type: str | None = None
    product: str | None = None
    contact_person: str | None = Field(default=None, max_length=200)
    contact_person_mobile: str | None = None
    address: str | None = Field(default=None, max_length=500)
    country: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    location_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)

    _blank = field_validator(
        "business_type", "product", "contact_person", "contact_person_mobile", "address",
        "country", "email", "location_url", "notes", mode="before",
    )(blank_to_none)

    @field_validator("business_type")
    @classmethod
    def _bt(cls, v):
        return _choice(v, BUSINESS_TYPES, "Business type")

    @field_validator("product")
    @classmethod
    def _pr(cls, v):
        return _choice(v, BUSINESS_TYPES, "Product")

    @field_validator("contact_person_mobile")
    @classmethod
    def _cpm(cls, v):
        return normalize_mobile(v) if v else v

    @field_validator("location_url")
    @classmethod
    def _url(cls, v):
        if v and not v.lower().startswith(("http://", "https://")):
            raise ValueError("Location URL must start with http:// or https://")
        return v


class CustomerCreate(CustomerBase):
    name: str = Field(min_length=1, max_length=200)
    mobile: str
    city: str = Field(min_length=1, max_length=100)
    salesman_id: int | None = None  # optional initial assignment (needs Customer.Assign)

    @field_validator("name", "city")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("This field is required")
        return v

    @field_validator("mobile")
    @classmethod
    def _mobile(cls, v):
        return normalize_mobile(v)


class CustomerUpdate(CustomerBase):
    name: str | None = Field(default=None, max_length=200)
    mobile: str | None = None
    city: str | None = Field(default=None, max_length=100)

    @field_validator("name", "city", "mobile")
    @classmethod
    def _req(cls, v, info):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be empty")
        return normalize_mobile(v) if info.field_name == "mobile" else v


class CustomerStatusIn(BaseModel):
    status: str

    _s = field_validator("status")(lambda v: _choice(v, CUSTOMER_STATUSES, "Status"))


class UserRef(ORM):
    id: int
    full_name: str


class AssigneeOut(ORM):
    id: int
    full_name: str
    assigned_at: UTCDateTime | None = None


class CustomerOut(ORM):
    id: int
    company_id: int
    name: str
    mobile: str
    business_type: str | None
    product: str | None
    contact_person: str | None
    contact_person_mobile: str | None
    address: str | None
    city: str
    country: str
    email: str | None
    location_url: str | None
    business_photo_url: str | None
    notes: str | None
    created_by_user_id: int
    status: str
    created_at: UTCDateTime
    updated_at: UTCDateTime
    assigned_salesman: AssigneeOut | None = None


class AssignmentIn(BaseModel):
    salesman_id: int


class AssignmentOut(BaseModel):
    id: int
    customer_id: int
    salesman_id: int
    salesman_name: str
    assigned_by_user_id: int
    assigned_by_name: str
    assigned_at: UTCDateTime
    ended_at: UTCDateTime | None
    is_active: bool


# ---------- Visits ----------
class VisitCreate(BaseModel):
    customer_id: int | None = None
    new_customer: CustomerCreate | None = None  # create a customer inside the visit workflow
    branch_id: int | None = None
    visit_time: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    purpose: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)
    outcome: str | None = None
    follow_up_date: datetime | None = None
    follow_up_notes: str | None = Field(default=None, max_length=4000)

    _blank = field_validator("purpose", "notes", "outcome", "follow_up_notes", mode="before")(blank_to_none)
    _utc = field_validator("visit_time", "follow_up_date")(to_naive_utc)

    @field_validator("outcome")
    @classmethod
    def _o(cls, v):
        return _choice(v, VISIT_OUTCOMES, "Outcome")

    @model_validator(mode="after")
    def _check(self):
        if (self.customer_id is None) == (self.new_customer is None):
            raise ValueError("Provide exactly one of customer_id or new_customer")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class VisitOut(ORM):
    id: int
    company_id: int
    customer_id: int
    customer_name: str | None = None
    user_id: int
    user_name: str | None = None
    branch_id: int | None
    branch_name: str | None = None
    visit_time: UTCDateTime
    latitude: float | None
    longitude: float | None
    purpose: str | None
    notes: str | None
    outcome: str | None
    photo_url: str | None
    created_at: UTCDateTime
    follow_up_id: int | None = None


# ---------- Follow-ups ----------
class FollowUpCreate(BaseModel):
    customer_id: int
    title: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)
    due_date: datetime

    model_config = {"extra": "forbid"}  # e.g. a fabricated branch_id is rejected, not silently stored

    _blank = field_validator("title", "notes", mode="before")(blank_to_none)
    _utc = field_validator("due_date")(to_naive_utc)


class FollowUpUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)
    due_date: datetime | None = None

    model_config = {"extra": "forbid"}
    _utc = field_validator("due_date")(to_naive_utc)


class FollowUpStatusIn(BaseModel):
    status: str
    outcome_text: str | None = Field(default=None, max_length=4000)

    _s = field_validator("status")(lambda v: _choice(v, FOLLOWUP_STATUSES, "Status"))
    _b = field_validator("outcome_text", mode="before")(blank_to_none)


class CompleteIn(BaseModel):
    outcome_text: str | None = Field(default=None, max_length=4000)
    _b = field_validator("outcome_text", mode="before")(blank_to_none)


class OutcomeIn(BaseModel):
    outcome_text: str = Field(min_length=1, max_length=4000)

    @field_validator("outcome_text")
    @classmethod
    def _t(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Outcome text is required")
        return v


class OutcomeOut(ORM):
    id: int
    follow_up_id: int
    outcome_text: str
    recorded_by_user_id: int
    recorded_by_name: str | None = None
    recorded_at: UTCDateTime
    attachment_url: str | None = None


class CustomerBrief(ORM):
    id: int
    name: str
    mobile: str
    city: str
    status: str


class FollowUpOut(ORM):
    id: int
    company_id: int
    customer_id: int
    user_id: int
    created_by_name: str | None = None
    visit_id: int | None
    title: str
    notes: str | None
    due_date: UTCDateTime
    status: str
    completed_at: UTCDateTime | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    is_overdue: bool = False
    customer: CustomerBrief | None = None
    assigned_salesman: AssigneeOut | None = None


class FollowUpDetail(FollowUpOut):
    outcomes: list[OutcomeOut] = []


class ActivityItem(BaseModel):
    type: str  # visit | follow_up | outcome | assignment
    at: UTCDateTime
    user_id: int | None
    user_name: str | None
    summary: str
    ref_id: int
