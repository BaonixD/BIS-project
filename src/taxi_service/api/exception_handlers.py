import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException as StarletteHTTPException

from taxi_service.core.errors import AppError
from taxi_service.core.request_id import REQUEST_ID_HEADER
from taxi_service.schemas.errors import ErrorBody, ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)


# Starlette types every handler by Exception; each one below is registered
# for a single exception class, so the cast only narrows the declared type.


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    return error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    status = HTTPStatus(error.status_code)
    message = error.detail if isinstance(error.detail, str) and error.detail else status.phrase
    return error_response(
        request,
        status_code=error.status_code,
        code=status.phrase.lower().replace(" ", "_").replace("-", "_"),
        message=message,
        headers=error.headers,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exc)
    # Only location, message and type: submitted input may contain passwords.
    errors: list[JsonValue] = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details={"errors": errors},
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # The request context is already reset here, so pass the ID explicitly.
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={"request_id": request.state.request_id},
    )
    return error_response(
        request,
        status_code=500,
        code="internal_error",
        message="Internal server error.",
    )


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, JsonValue] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id: str = request.state.request_id
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=dict(details or {})),
        request_id=request_id,
    )
    # Set explicitly: 500 responses are sent outside RequestIdMiddleware.
    response_headers = {**(headers or {}), REQUEST_ID_HEADER: request_id}
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=response_headers,
    )
