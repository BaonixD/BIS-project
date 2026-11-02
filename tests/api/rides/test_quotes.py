"""POST /api/v1/rides/quotes: a passenger's priced road route, valid for five minutes."""

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from support.auth import CSRF_HEADER, register_and_login
from support.clock import ManualClock
from support.drivers import create_admin, login_as
from support.rides import ABAY_DOSTYK, AL_FARABI, QUOTE_BODY, QUOTES_URL, count_rows
from support.routing import FakeRoutingProvider, fake_route
from taxi_service.core.errors import AppError
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.rides.models import RideQuote

PICKUP, DROPOFF = Coordinates(**ABAY_DOSTYK), Coordinates(**AL_FARABI)
QUOTE_TTL = timedelta(minutes=5)


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def stored_quotes(session_factory: SessionFactory) -> list[RideQuote]:
    async with session_factory() as session, read_transaction(session):
        return list(await session.scalars(select(RideQuote)))


# Successful quote


async def test_passenger_gets_a_priced_quote(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")

    response = await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "quote_id",
        "pickup",
        "dropoff",
        "route",
        "amount_kzt",
        "currency",
        "tariff_version",
        "created_at",
        "expires_at",
    }
    assert (body["amount_kzt"], body["currency"], body["tariff_version"]) == (2200, "KZT", "edu-v1")
    assert body["pickup"] == ABAY_DOSTYK
    assert body["dropoff"] == AL_FARABI
    assert body["route"] == fake_route(PICKUP, DROPOFF).model_dump(mode="json")
    assert datetime.fromisoformat(body["created_at"]) == clock.now()
    assert datetime.fromisoformat(body["expires_at"]) == clock.now() + QUOTE_TTL
    assert routing_provider.calls == [(PICKUP, DROPOFF)]


async def test_quote_is_stored_for_the_passenger(
    client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")

    body = (await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)).json()

    [quote] = await stored_quotes(session_factory)
    route = fake_route(PICKUP, DROPOFF)
    assert str(quote.id) == body["quote_id"]
    assert quote.passenger_id == passenger.id
    assert (quote.pickup_longitude, quote.pickup_latitude) == PICKUP.as_lon_lat()
    assert (quote.dropoff_longitude, quote.dropoff_latitude) == DROPOFF.as_lon_lat()
    assert (quote.distance_m, quote.duration_s, quote.provider) == (10_000, 1_500, "fake")
    assert quote.route_geometry == route.route_geometry.model_dump(mode="json")
    assert (quote.amount_kzt, quote.currency, quote.tariff_version) == (2200, "KZT", "edu-v1")
    assert (quote.created_at, quote.expires_at) == (clock.now(), clock.now() + QUOTE_TTL)


async def test_quote_price_follows_the_route_metrics(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    route = fake_route(PICKUP, DROPOFF).model_copy(update={"distance_m": 1000, "duration_s": 60})
    routing_provider.route = route
    passenger = await register_and_login(client, "pat")

    body = (await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)).json()

    assert body["amount_kzt"] == 800  # minimum fare of edu-v1
    assert body["route"]["distance_m"] == 1000


async def test_quote_lifetime_starts_when_the_route_is_known(
    app: FastAPI, client: httpx.AsyncClient, clock: ManualClock
) -> None:
    class SlowProvider(FakeRoutingProvider):
        async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
            clock.advance(timedelta(seconds=3))
            return await super().get_route(origin, destination)

    app.state.routing_provider = SlowProvider()
    passenger = await register_and_login(client, "pat")
    started = clock.now()

    body = (await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)).json()

    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at == started + timedelta(seconds=3)
    assert datetime.fromisoformat(body["expires_at"]) == created_at + QUOTE_TTL


async def test_no_database_connection_is_held_while_routing(
    app: FastAPI, client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    checked_out: list[int] = []

    class PoolProbe:
        async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
            checked_out.append(app.state.engine.pool.checkedout())
            return await routing_provider.get_route(origin, destination)

    app.state.routing_provider = PoolProbe()
    passenger = await register_and_login(client, "pat")

    response = await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)

    assert response.status_code == 201
    assert checked_out == [0]


# Who may ask


async def test_quote_needs_a_session(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    response = await client.post(QUOTES_URL, json=QUOTE_BODY)

    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"
    assert routing_provider.call_count == 0


async def test_quote_needs_the_csrf_token(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    await register_and_login(client, "pat")

    response = await client.post(QUOTES_URL, json=QUOTE_BODY, headers={CSRF_HEADER: "wrong"})

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"
    assert routing_provider.call_count == 0


@pytest.mark.parametrize("role", ["driver", "admin"])
async def test_only_a_passenger_gets_a_quote(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    routing_provider: FakeRoutingProvider,
    role: str,
) -> None:
    if role == "admin":
        await create_admin(app, session_factory, clock)
        user = await login_as(client, "admin")
    else:
        user = await register_and_login(client, "dana", role="driver")

    response = await client.post(QUOTES_URL, json=QUOTE_BODY, headers=user.csrf_headers)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert routing_provider.call_count == 0
    assert await count_rows(session_factory, RideQuote) == 0


# Routing errors pass through and store nothing


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RoutingUnavailableError(), 503, "routing_unavailable"),
        (RoutingProviderError("timeout"), 503, "routing_provider_error"),
        (RouteNotFoundError(), 422, "route_not_found"),
    ],
)
async def test_routing_error_passes_through_without_a_quote(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    routing_provider: FakeRoutingProvider,
    error: AppError,
    status: int,
    code: str,
) -> None:
    routing_provider.fail_with(error)
    passenger = await register_and_login(client, "pat")

    response = await client.post(QUOTES_URL, json=QUOTE_BODY, headers=passenger.csrf_headers)

    assert response.status_code == status
    assert error_code(response) == code
    assert await count_rows(session_factory, RideQuote) == 0


async def test_identical_points_are_rejected_without_routing(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    routing_provider: FakeRoutingProvider,
) -> None:
    passenger = await register_and_login(client, "pat")

    response = await client.post(
        QUOTES_URL,
        json={"pickup": ABAY_DOSTYK, "dropoff": ABAY_DOSTYK},
        headers=passenger.csrf_headers,
    )

    assert response.status_code == 422
    assert error_code(response) == "route_points_identical"
    assert routing_provider.call_count == 0
    assert await count_rows(session_factory, RideQuote) == 0


# Request validation


@pytest.mark.parametrize(
    "body",
    [
        {"pickup": ABAY_DOSTYK},
        {"origin": ABAY_DOSTYK, "destination": AL_FARABI},
        {**QUOTE_BODY, "amount_kzt": 100},
        {**QUOTE_BODY, "tariff_version": "free"},
        {"pickup": {"longitude": 76.9, "latitude": 90.5}, "dropoff": AL_FARABI},
        {"pickup": {"longitude": "76.9", "latitude": 43.2}, "dropoff": AL_FARABI},
        {"pickup": [76.9572, 43.2389], "dropoff": AL_FARABI},
    ],
)
async def test_invalid_quote_request_is_rejected(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider, body: Any
) -> None:
    passenger = await register_and_login(client, "pat")

    response = await client.post(QUOTES_URL, json=body, headers=passenger.csrf_headers)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert routing_provider.call_count == 0
