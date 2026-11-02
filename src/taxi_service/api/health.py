from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from taxi_service.core.errors import AppError
from taxi_service.schemas.errors import ErrorResponse

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/live")
async def live() -> HealthStatus:
    return HealthStatus()


@router.get(
    "/ready",
    responses={503: {"model": ErrorResponse, "description": "A required dependency is not ready"}},
)
async def ready() -> HealthStatus:
    # No database is wired in yet (T01); never report a dependency as ready untested.
    raise AppError(
        status_code=503,
        code="database_not_configured",
        message="Database connection is not configured yet.",
    )
