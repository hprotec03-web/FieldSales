from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.context import CurrentUser
from app.db.session import get_db
from app.services import dashboard as svc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(tz_offset_minutes: int = Query(0, ge=-840, le=840, description="Client UTC offset, e.g. 240 for Dubai"),
              ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Role-specific dashboard (kind = admin | manager | salesman), computed live from the database."""
    return svc.build(db, ctx, tz_offset_minutes)
