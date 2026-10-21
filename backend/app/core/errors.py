import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("eventhub")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details


def bad_request(code, msg): return AppError(400, code, msg)
def unauthorized(code, msg): return AppError(401, code, msg)
def forbidden(code, msg): return AppError(403, code, msg)
def conflict(code, msg): return AppError(409, code, msg)
def not_found(what): return AppError(404, "NOT_FOUND", f"{what} not found.")


def _body(code, message, details=None):
    err = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"success": False, "error": err}


def register_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def _app(_: Request, e: AppError):
        return JSONResponse(_body(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        codes = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(_body(codes.get(e.status_code, "HTTP_ERROR"), str(e.detail)), status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, e: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in x["loc"][1:]), "message": x["msg"]} for x in e.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Request validation failed.", details), status_code=422)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, e: IntegrityError):
        log.warning("integrity error: %s", e.orig)
        return JSONResponse(_body("CONFLICT", "The request conflicts with existing data."), status_code=409)

    @app.exception_handler(Exception)
    async def _any(_: Request, e: Exception):
        log.exception("Unhandled error")
        return JSONResponse(_body("INTERNAL_ERROR", "An unexpected error occurred."), status_code=500)
