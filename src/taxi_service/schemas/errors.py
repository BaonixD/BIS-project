from typing import Any

from pydantic import BaseModel, Field, JsonValue


class ErrorBody(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Resource not found."])
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Unified error envelope returned by every non-2xx API response."""

    error: ErrorBody
    request_id: str


_ERROR_DESCRIPTIONS = {
    401: "Not authenticated (no or expired session) or invalid credentials",
    403: "Forbidden: role, CSRF token or request origin not allowed",
    404: "Not found or not accessible",
    409: "Conflict with the current state",
    422: "Request validation failed; details.errors lists loc, msg and type",
    429: "Too many attempts; details.retry_after_seconds",
    500: "Internal server error",
    503: "A required service is unavailable",
}


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries with the unified error envelope."""
    return {
        status: {"model": ErrorResponse, "description": _ERROR_DESCRIPTIONS[status]}
        for status in statuses
    }
