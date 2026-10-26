"""Application settings, loaded from environment variables / .env (never commit real secrets)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FieldSales API"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    # --- Database (SQL Server) ---
    db_server: str = "localhost"
    db_port: int = 1433
    db_name: str = "FieldSales"
    db_user: str = "sa"
    db_password: str = ""
    db_driver: str = "ODBC Driver 18 for SQL Server"
    db_trust_server_certificate: bool = True
    # Full SQLAlchemy URL override (used by tests / alternative engines). Leave empty for SQL Server.
    database_url: str = ""

    # --- Security ---
    jwt_secret: str = Field(default="change-me-in-env", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    cookie_name: str = "fs_access"
    csrf_cookie_name: str = "fs_csrf"
    cookie_secure: bool = False  # set True behind HTTPS
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cors_origins: str = "http://localhost:5173"

    login_max_attempts: int = 5
    login_window_seconds: int = 300

    # --- Business rules ---
    # How duplicate customers are detected inside one company:
    #   mobile       -> same mobile number            (default)
    #   name_mobile  -> same name AND same mobile
    #   name         -> same name
    #   off          -> no duplicate detection
    duplicate_rule: Literal["mobile", "name_mobile", "name", "off"] = "mobile"
    default_country: str = "United Arab Emirates"

    # --- Files ---
    upload_dir: str = "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    image_max_dimension: int = 1600

    @property
    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        query = {"driver": self.db_driver}
        if self.db_trust_server_certificate:
            query["TrustServerCertificate"] = "yes"
        return URL.create(
            "mssql+pyodbc",
            username=self.db_user,
            password=self.db_password,
            host=self.db_server,
            port=self.db_port,
            database=self.db_name,
            query=query,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
