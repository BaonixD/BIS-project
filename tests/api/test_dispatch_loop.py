"""The dispatch loop runs inside the application lifespan; all search state is in the database.

The loop is switched off for tests in general (``DISPATCH_LOOP_ENABLED=false`` in
conftest). Here it runs with a 10 ms interval for a short, bounded time; the clock
is still the manual one, so offers expire only when a test moves it.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher, accept_url
from support.drivers import DriverFactory, login_as
from support.rides import order_ride
from support.routing import FakeRoutingProvider
from taxi_service.core.config import Settings
from taxi_service.main import create_app
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.dispatch import DispatchService
from taxi_service.modules.rides.states import OfferStatus, RideStatus

NEAR_PICKUP = Coordinates(longitude=76.9580, latitude=43.2389)
FARTHER = Coordinates(longitude=76.9650, latitude=43.2389)
TTL = timedelta(seconds=30)
WAIT_S = 3.0
POLL_S = 0.01
LOOP = {"dispatch_loop_enabled": True, "dispatch_interval_s": 0.01}


@asynccontextmanager
async def running(
    settings: Settings, clock: ManualClock, **changes: Any
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    """A fresh application on the test database with its lifespan running."""
    app = create_app(
        settings.model_copy(update=changes), clock=clock, routing_provider=FakeRoutingProvider()
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            yield app, client


class RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


async def eventually(check: Callable[[], Awaitable[bool]]) -> None:
    """Poll ``check`` every 10 ms for at most ``WAIT_S`` seconds."""
    for _ in range(int(WAIT_S / POLL_S)):
        if await check():
            return
        await asyncio.sleep(POLL_S)
    raise AssertionError("the loop did not reach the expected state")


async def test_loop_is_off_unless_enabled(settings: Settings, clock: ManualClock) -> None:
    assert settings.dispatch_loop_enabled is False

    async with running(settings, clock) as (app, _):
        assert app.state.dispatch_loop is None


async def test_loop_expires_offers_and_asks_the_next_driver(
    settings: Settings,
    clock: ManualClock,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
) -> None:
    near = await driver_factory.driver("near", location=NEAR_PICKUP)
    farther = await driver_factory.driver("farther", location=FARTHER)

    async with running(settings, clock, **LOOP) as (app, client):
        passenger = await register_and_login(client, "pat")
        ride_id = uuid.UUID((await order_ride(client, passenger))["id"])
        clock.advance(TTL)

        async def moved_on() -> bool:
            return [(o.driver_id, o.status) for o in await dispatcher.offers(ride_id)] == [
                (near, OfferStatus.EXPIRED),
                (farther, OfferStatus.PENDING),
            ]

        await eventually(moved_on)
        loop = app.state.dispatch_loop
        assert loop.running

    assert not loop.running


async def test_loop_keeps_running_after_a_failed_pass(
    settings: Settings,
    clock: ManualClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def flaky(self: DispatchService, *args: object) -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database hiccup")
        return 0

    monkeypatch.setattr(DispatchService, "process_due", flaky)

    handler = RecordingHandler()
    loop_logger = logging.getLogger("taxi_service.modules.rides.dispatch_loop")
    loop_logger.addHandler(handler)
    try:
        async with running(settings, clock, **LOOP):

            async def retried() -> bool:
                return len(calls) >= 3

            await eventually(retried)
    finally:
        loop_logger.removeHandler(handler)

    [failure] = [record for record in handler.records if record.levelno == logging.ERROR]
    assert failure.getMessage().startswith("Dispatch pass failed")
    assert failure.exc_info is not None
    stopped_at = len(calls)
    await asyncio.sleep(0.05)
    assert len(calls) == stopped_at


async def test_loop_does_not_create_a_missing_database_file(
    tmp_path: Path, settings: Settings, clock: ManualClock
) -> None:
    missing = tmp_path / "missing.db"

    async with running(settings, clock, database_url=f"sqlite+aiosqlite:///{missing}", **LOOP) as (
        app,
        _,
    ):
        await asyncio.sleep(0.05)
        assert app.state.dispatch_loop.running

    assert not missing.exists()


async def test_restart_after_the_deadline_restores_the_search_without_double_assignment(
    settings: Settings,
    clock: ManualClock,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
) -> None:
    near = await driver_factory.driver("near", location=NEAR_PICKUP)
    farther = await driver_factory.driver("farther", location=FARTHER)
    async with running(settings, clock) as (_, client):
        passenger = await register_and_login(client, "pat")
        ride_id = uuid.UUID((await order_ride(client, passenger))["id"])
        [first] = await dispatcher.offers(ride_id)
    clock.advance(TTL)  # the application is down when the offer runs out
    await driver_factory.move(near, NEAR_PICKUP)
    await driver_factory.move(farther, FARTHER)

    async with running(settings, clock, **LOOP) as (_, client):

        async def recovered() -> bool:
            return len(await dispatcher.offers(ride_id)) == 2

        await eventually(recovered)
        late = await login_as(client, "near")
        refused = await client.post(accept_url(first.id), headers=late.csrf_headers)
        second = await dispatcher.pending(ride_id)
        assert second is not None
        driver = await login_as(client, "farther")
        accepted = await client.post(accept_url(second.id), headers=driver.csrf_headers)
        await asyncio.sleep(0.05)  # a few more loop passes

    assert (first.driver_id, refused.status_code) == (near, 409)
    assert refused.json()["error"]["code"] == "offer_expired"
    assert (second.driver_id, accepted.status_code) == (farther, 200)
    assert [(o.driver_id, o.status) for o in await dispatcher.offers(ride_id)] == [
        (near, OfferStatus.EXPIRED),
        (farther, OfferStatus.ACCEPTED),
    ]
    ride = await dispatcher.ride(ride_id)
    assert (ride.status, ride.driver_id) == (RideStatus.ASSIGNED, farther)
