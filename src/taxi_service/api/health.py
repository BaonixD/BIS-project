from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from taxi_service.core.errors import AppError
from taxi_service.database.readiness import DatabaseReadiness, check_database
from taxi_service.schemas.errors import ErrorResponse

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyStatus(BaseModel):
    status: Literal["ready"] = "ready"


# Error code and message per state; the database URL is never part of the response.
_NOT_READY: dict[DatabaseReadiness, tuple[str, str]] = {
    DatabaseReadiness.UNAVAILABLE: ("database_unavailable", "Database is not reachable."),
    DatabaseReadiness.NOT_MIGRATED: (
        "database_not_migrated",
        "Database schema is not at the latest migration; run alembic upgrade head.",
    ),
}


@router.get("/live")
async def live() -> HealthStatus:
    return HealthStatus()


@router.get(
    "/ready",
    responses={503: {"model": ErrorResponse, "description": "The database is not ready"}},
)
async def ready(request: Request) -> ReadyStatus:
    readiness = await check_database(request.app.state.engine, request.app.state.migration_heads)
    if readiness is not DatabaseReadiness.READY:
        code, message = _NOT_READY[readiness]
        raise AppError(status_code=503, code=code, message=message)
    return ReadyStatus()
