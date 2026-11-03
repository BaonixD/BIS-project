"""Quotes and rides through the real API, or through the services (``RideFactory``).

Usage in an API test with the ``client`` fixture (the fake route costs 2200 KZT)::

    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    ride = await order_ride(client, passenger)          # quote + ride, status "searching"
    response = await client.get(ride_url(ride["id"]))

Without HTTP (fixture ``ride_factory``): ``ride = await ride_factory.searching_ride()``.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import func, select

from support.auth import PASSWORD, LoggedInUser
from support.clock import ManualClock
from support.routing import FakeRoutingProvider
from taxi_service.database.base import Base
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides import service as rides_service
from taxi_service.modules.rides.idempotency import IDEMPOTENCY_HEADER
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.schemas import QuoteRequest, RideCreateRequest
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import UserRole

RIDES_URL = "/api/v1/rides"
QUOTES_URL = f"{RIDES_URL}/quotes"

ABAY_DOSTYK = {"longitude": 76.9572, "latitude": 43.2389}
AL_FARABI = {"longitude": 76.9286, "latitude": 43.2187}
QUOTE_BODY = {"pickup": ABAY_DOSTYK, "dropoff": AL_FARABI}
PICKUP, DROPOFF = Coordinates(**ABAY_DOSTYK), Coordinates(**AL_FARABI)


def ride_url(ride_id: uuid.UUID | str) -> str:
    return f"{RIDES_URL}/{ride_id}"


def ride_headers(user: LoggedInUser, key: str | None = None) -> dict[str, str]:
    """CSRF header plus an ``Idempotency-Key`` (a new random one unless given)."""
    return {**user.csrf_headers, IDEMPOTENCY_HEADER: key or uuid.uuid4().hex}


async def request_quote(
    client: httpx.AsyncClient, user: LoggedInUser, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = await client.post(QUOTES_URL, json=body or QUOTE_BODY, headers=user.csrf_headers)
    assert response.status_code == 201, response.text
    quote: dict[str, Any] = response.json()
    return quote


def ride_body(
    quote_id: str, payment_method: str | None = None, tariff: str | None = None
) -> dict[str, Any]:
    """``POST /rides`` body; the server takes cash and economy for omitted fields."""
    body: dict[str, Any] = {"quote_id": quote_id}
    if payment_method is not None:
        body["payment_method"] = payment_method
    if tariff is not None:
        body["tariff"] = tariff
    return body


async def order_ride(
    client: httpx.AsyncClient,
    user: LoggedInUser,
    *,
    key: str | None = None,
    payment_method: str | None = None,
    tariff: str | None = None,
) -> dict[str, Any]:
    """New quote, then a ride from it; the client must be logged in as ``user``."""
    quote = await request_quote(client, user)
    response = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], payment_method, tariff),
        headers=ride_headers(user, key),
    )
    assert response.status_code == 201, response.text
    ride: dict[str, Any] = response.json()
    return ride


async def count_rows(session_factory: SessionFactory, model: type[Base]) -> int:
    async with session_factory() as session, read_transaction(session):
        total = await session.scalar(select(func.count()).select_from(model))
    return total or 0


@dataclass
class RideFactory:
    """Passengers and ``searching`` rides through the services, without HTTP (dispatch tests).

    Fixture ``ride_factory``; the route comes from its own ``FakeRoutingProvider``
    (2200 KZT). Usage::

        ride = await ride_factory.searching_ride(pickup=Coordinates(**ALMATY_CENTER))
        assert ride.status is RideStatus.SEARCHING and ride.driver_id is None
    """

    session_factory: SessionFactory
    clock: ManualClock
    hasher: PasswordHasher
    routing: FakeRoutingProvider = field(default_factory=FakeRoutingProvider)
    _passengers: int = 0

    async def passenger(self, username: str | None = None) -> uuid.UUID:
        self._passengers += 1
        async with self.session_factory() as db:
            user = await users_service.create_user(
                db,
                username or f"passenger_{self._passengers}",
                PASSWORD,
                UserRole.PASSENGER,
                clock=self.clock,
                hasher=self.hasher,
            )
        return user.id

    async def searching_ride(
        self,
        passenger_id: uuid.UUID | None = None,
        *,
        pickup: Coordinates = PICKUP,
        dropoff: Coordinates = DROPOFF,
        tariff: Tariff = Tariff.ECONOMY,
    ) -> Ride:
        """Quote and ride for ``passenger_id`` (a new passenger if omitted)."""
        passenger_id = passenger_id or await self.passenger()
        async with self.session_factory() as session:
            quote = await rides_service.create_quote(
                session,
                passenger_id,
                QuoteRequest(pickup=pickup, dropoff=dropoff),
                clock=self.clock,
                routing=self.routing,
            )
            creation = await rides_service.create_ride(
                session,
                passenger_id,
                RideCreateRequest(quote_id=quote.id, tariff=tariff),
                uuid.uuid4().hex,
                clock=self.clock,
            )
        return creation.ride
