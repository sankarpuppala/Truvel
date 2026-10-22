"""Error shape: {"error": {"code", "message", "detail"}} (SPEC §11)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request


class ApiError(HTTPException):
    """An error the client is meant to show to the user."""

    def __init__(self, status: int, code: str, message: str, detail: Any = None):
        super().__init__(status_code=status, detail=message)
        self.code = code
        self.message = message
        self.extra = detail


def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.extra}},
    )


def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": str(exc.detail),
                "detail": None,
            }
        },
    )


def bad_request(message: str, code: str = "bad_request", detail: Any = None) -> ApiError:
    return ApiError(400, code, message, detail)


def unauthorized(message: str = "Sign in to do that.") -> ApiError:
    return ApiError(401, "unauthorized", message)


def forbidden(message: str, code: str = "forbidden") -> ApiError:
    return ApiError(403, code, message)


def not_found(message: str = "Not found.", code: str = "not_found") -> ApiError:
    return ApiError(404, code, message)


def too_many(message: str, code: str = "rate_limited") -> ApiError:
    return ApiError(429, code, message)


def conflict(message: str, code: str = "conflict", detail: Any = None) -> ApiError:
    return ApiError(409, code, message, detail)
