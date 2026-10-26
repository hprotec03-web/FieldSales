"""Domain exceptions + centralized handlers returning a consistent error envelope:
{"error": {"code": "...", "message": "...", "details": ...}}"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("fieldsales")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str = "", details=None):
        super().__init__(message)
        self.message = message or self.__class__.__name__
        self.details = details


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class Unauthorized(AppError):
    status_code, code = 401, "unauthorized"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class InvalidRelation(AppError):
    status_code, code = 422, "invalid_relationship"


class TooManyRequests(AppError):
    status_code, code = 429, "too_many_requests"


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_handlers(app: FastAPI, debug: bool = False) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(_body(exc.code, exc.message, exc.details), exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(_body("validation_error", "Invalid request", details), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_body("http_error", str(exc.detail)), exc.status_code)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        log.warning("Integrity error: %s", exc.__class__.__name__)  # no SQL/params in logs
        return JSONResponse(_body("conflict", "The change conflicts with existing data"), 409)

    @app.exception_handler(SQLAlchemyError)
    async def _db(_: Request, exc: SQLAlchemyError):
        log.error("Database error: %s", exc.__class__.__name__)
        return JSONResponse(_body("database_error", "A database error occurred"), 500)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(_body("server_error", "Internal server error"), 500)
