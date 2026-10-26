from fastapi import APIRouter

from app.api.v1 import (assignments, auth, branches, companies, customers, dashboard, files, followups, reports, users,
                        visits)

api_router = APIRouter(prefix="/api/v1")
for m in (auth, companies, branches, users, customers, assignments, visits, followups, dashboard, reports, files):
    api_router.include_router(m.router)
