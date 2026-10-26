import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exceptions import register_handlers
from app.db.session import get_engine


def create_app() -> FastAPI:
    s = get_settings()
    logging.basicConfig(level=logging.DEBUG if s.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if s.environment == "production" and (s.jwt_secret == "change-me-in-env" or len(s.jwt_secret) < 32):
        raise RuntimeError("Set a strong JWT_SECRET (>= 32 chars) in production")

    app = FastAPI(title=s.app_name, version="1.0.0", docs_url="/docs", openapi_url="/openapi.json")
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
        allow_methods=["*"], allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    register_handlers(app, s.debug)
    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    def health():
        """Liveness probe (no database access)."""
        return {"status": "ok"}

    @app.get("/health/db", tags=["health"])
    def health_db():
        """Readiness probe: verifies SQL Server connectivity."""
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}

    return app


app = create_app()
