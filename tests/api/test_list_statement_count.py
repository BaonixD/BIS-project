"""Ride and user lists cost the same number of SQL statements for 10 and 30 items (no N+1).

Statements are counted on the application's own engine for a whole request,
the session lookup of authentication included; ``queries`` leaves out the
PRAGMA and BEGIN of each read transaction.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.drivers import ADMIN_DRIVERS_URL, DriverFactory, login_as
from support.history import (
    ADMIN_RIDES_URL,
    ADMIN_USERS_URL,
    StatementCounter,
    count_statements,
    past_rides,
)
from support.rides import RIDES_URL, RideFactory
from taxi_service.modules.rides.states import RideStatus

# One for authentication (session joined with its user), the page and its total.
MAX_QUERIES = 3

Seed = Callable[[int], Awaitable[None]]


async def statements_for_page(
    app: FastAPI, client: httpx.AsyncClient, url: str, expected_items: int
) -> StatementCounter:
    with count_statements(app.state.engine) as counter:
        response = await client.get(url, params={"limit": 100})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert len(body["items"]) == expected_items
    return counter


async def assert_constant_statements(
    app: FastAPI, client: httpx.AsyncClient, url: str, seed: Seed, *, already: int = 0
) -> None:
    await seed(10)
    small = await statements_for_page(app, client, url, already + 10)
    await seed(20)
    large = await statements_for_page(app, client, url, already + 30)

    assert len(small) == len(large)
    assert large.queries <= MAX_QUERIES


@pytest.fixture
async def admin_id(driver_factory: DriverFactory) -> uuid.UUID:
    return await driver_factory.admin_id()


async def test_passenger_history(
    app: FastAPI, client: httpx.AsyncClient, ride_factory: RideFactory
) -> None:
    pat = await ride_factory.passenger("pat")
    await login_as(client, "pat")

    async def seed(count: int) -> None:
        await past_rides(ride_factory, pat, count)

    await assert_constant_statements(app, client, RIDES_URL, seed)


async def test_driver_history(
    app: FastAPI,
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
) -> None:
    dana = await driver_factory.driver("dana")
    pat = await ride_factory.passenger("pat")
    await login_as(client, "dana")

    async def seed(count: int) -> None:
        await past_rides(ride_factory, pat, count, status=RideStatus.COMPLETED, driver_id=dana)

    await assert_constant_statements(app, client, RIDES_URL, seed)


async def test_admin_rides(
    app: FastAPI, client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    await login_as(client, "admin")

    async def seed(count: int) -> None:
        for _ in range(count):
            await past_rides(ride_factory, await ride_factory.passenger(), 1)

    await assert_constant_statements(app, client, ADMIN_RIDES_URL, seed)


async def test_admin_users(
    app: FastAPI, client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    await login_as(client, "admin")

    async def seed(count: int) -> None:
        for _ in range(count):
            await ride_factory.passenger()

    await assert_constant_statements(app, client, ADMIN_USERS_URL, seed, already=1)


async def test_admin_drivers_with_their_ratings(
    app: FastAPI, client: httpx.AsyncClient, driver_factory: DriverFactory, admin_id: uuid.UUID
) -> None:
    await login_as(client, "admin")
    created = 0

    async def seed(count: int) -> None:
        nonlocal created
        for _ in range(count):
            created += 1
            await driver_factory.driver(f"driver_{created}")

    await seed(10)
    small = await statements_for_page(app, client, ADMIN_DRIVERS_URL, 10)
    await seed(20)
    large = await statements_for_page(app, client, ADMIN_DRIVERS_URL, 30)

    assert len(small) == len(large)
    # The ratings of the whole page come from one grouped query.
    assert large.queries <= MAX_QUERIES + 1
    assert any("ride_ratings" in statement for statement in large.statements)
