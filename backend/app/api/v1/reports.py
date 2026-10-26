from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CurrentUser
from app.db.session import get_db
from app.repositories.scopes import get_customer
from app.services import reports as svc
from app.utils.time import zulu

router = APIRouter(prefix="/reports", tags=["reports"])
Fmt = Query("json", pattern="^(json|csv)$", description="json (default) or csv download")


def _emit(cols, rows, fmt, name):
    if fmt == "csv":
        return svc.csv_response(cols, rows, f"{name}.csv")
    return {"columns": [{"key": k, "label": l} for k, l in cols], "rows": zulu(rows), "total": len(rows)}


@router.get("/customers")
def customers(status: str | None = None, city: str | None = None, business_type: str | None = None,
              salesman_id: int | None = None, format: str = Fmt,
              ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    return _emit(*svc.customers_report(db, ctx, status, city, business_type, salesman_id), format, "customers")


@router.get("/assignments")
def assignments(date_from: date | None = None, date_to: date | None = None, salesman_id: int | None = None, format: str = Fmt,
                ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    return _emit(*svc.assignments_report(db, ctx, date_from, date_to, salesman_id), format, "assignments")


@router.get("/visits")
def visits(date_from: date | None = None, date_to: date | None = None, salesman_id: int | None = None,
           customer_id: int | None = None, outcome: str | None = None, format: str = Fmt,
           ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    return _emit(*svc.visits_report(db, ctx, date_from, date_to, salesman_id, customer_id, outcome), format, "visits")


@router.get("/salesman-activity")
def salesman_activity(date_from: date | None = None, date_to: date | None = None, format: str = Fmt,
                      ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    return _emit(*svc.salesman_activity_report(db, ctx, date_from, date_to), format, "salesman-activity")


@router.get("/followups")
def followups(status: str | None = None, overdue: bool | None = None, date_from: date | None = None,
              date_to: date | None = None, salesman_id: int | None = None, customer_id: int | None = None, format: str = Fmt,
              ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    """Pending = ?status=Pending, overdue = ?overdue=true, completed = ?status=Completed (date range applies to due date)."""
    return _emit(*svc.followups_report(db, ctx, status, overdue, date_from, date_to, salesman_id, customer_id), format, "followups")


@router.get("/customer-activity")
def customer_activity(customer_id: int, format: str = Fmt,
                      ctx: CurrentUser = Depends(require_permission("Reports.View")), db: Session = Depends(get_db)):
    customer = get_customer(db, ctx, customer_id)
    return _emit(*svc.customer_activity_report(db, ctx, customer), format, f"customer-{customer.id}-activity")
