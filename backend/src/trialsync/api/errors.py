from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: str
    field: str | None = None
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ApplicationError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid4()))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            trace_id=get_trace_id(request),
            field=field,
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request, exception: ApplicationError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=exception.status_code,
            code=exception.code,
            message=exception.message,
            field=exception.field,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=422,
            code="REQUEST_VALIDATION_ERROR",
            message="The request could not be validated.",
            details=list(exception.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exception: StarletteHTTPException
    ) -> JSONResponse:
        code = "RESOURCE_NOT_FOUND" if exception.status_code == 404 else "HTTP_ERROR"
        message = (
            "The requested resource was not found."
            if exception.status_code == 404
            else str(exception.detail)
        )
        return error_response(
            request,
            status_code=exception.status_code,
            code=code,
            message=message,
        )
