"""The application owns one Clock: injectable in create_app, exposed as a dependency."""

from datetime import timedelta

import httpx
from fastapi import APIRouter

from support.clock import ManualClock
from taxi_service.core.clock import ClockDep, SystemClock
from taxi_service.core.config import Settings
from taxi_service.main import create_app

SETTINGS = Settings(_env_file=None, database_url="sqlite+aiosqlite:///./unused-test.db")


def _probe_router() -> APIRouter:
    router = APIRouter(prefix="/_probe")

    @router.get("/now")
    async def read_now(clock: ClockDep) -> dict[str, str]:
        return {"now": clock.now().isoformat()}

    return router


def test_app_uses_system_clock_by_default() -> None:
    assert isinstance(create_app(SETTINGS).state.clock, SystemClock)


async def test_injected_clock_is_served_by_dependency() -> None:
    clock = ManualClock()
    app = create_app(SETTINGS, clock=clock)
    app.include_router(_probe_router())
    clock.advance(timedelta(minutes=5))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_probe/now")

    assert response.json() == {"now": clock.now().isoformat()}
