from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.context import CurrentUser
from app.core.exceptions import NotFound
from app.db.session import get_db
from app.models import Customer, Visit
from app.repositories.scopes import customers_stmt, visits_stmt
from app.services.storage import get_storage

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{folder}/{name}")
def get_file(folder: str, name: str, ctx: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Private files: served only when the DB row that references the file is visible to the caller."""
    url = f"/api/v1/files/{folder}/{name}"
    if folder == "customers":
        owner = db.scalars(customers_stmt(ctx).where(Customer.business_photo_url == url)).first()
    elif folder == "visits":
        owner = db.scalars(visits_stmt(ctx).where(Visit.photo_url == url)).first()
    else:
        owner = None
    if not owner:
        raise NotFound("File not found")
    path = get_storage().open_path(folder, name)  # raises on traversal / bad names
    if not path:
        raise NotFound("File not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
