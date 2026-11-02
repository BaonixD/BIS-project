from collections.abc import Mapping
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import JsonValue

from taxi_service.core.errors import AppError
from taxi_service.core.request_id import REQUEST_ID_HEADER
from taxi_service.schemas.errors import ErrorBody, ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    # Starlette types handlers by Exception; this one is registered for AppError only.
    error = cast(AppError, exc)
    return error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, JsonValue] | None = None,
) -> JSONResponse:
    request_id: str = request.state.request_id
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=dict(details or {})),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: request_id},
    )
