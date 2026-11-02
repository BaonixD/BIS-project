"""Quotes and rides through the real API.

Usage in an API test with the ``client`` fixture (the fake route costs 2200 KZT)::

    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    ride = await order_ride(client, passenger)          # quote + ride, status "searching"
    response = await client.get(ride_url(ride["id"]))
"""

import uuid
from typing import Any

import httpx
from sqlalchemy import func, select

from support.auth import LoggedInUser
from taxi_service.database.base import Base
from taxi_service.database.session import SessionFactory, read_transaction

RIDES_URL = "/api/v1/rides"
QUOTES_URL = f"{RIDES_URL}/quotes"
IDEMPOTENCY_HEADER = "Idempotency-Key"

ABAY_DOSTYK = {"longitude": 76.9572, "latitude": 43.2389}
AL_FARABI = {"longitude": 76.9286, "latitude": 43.2187}
QUOTE_BODY = {"pickup": ABAY_DOSTYK, "dropoff": AL_FARABI}


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


async def order_ride(
    client: httpx.AsyncClient, user: LoggedInUser, *, key: str | None = None
) -> dict[str, Any]:
    """New quote, then a ride from it; the client must be logged in as ``user``."""
    quote = await request_quote(client, user)
    response = await client.post(
        RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=ride_headers(user, key)
    )
    assert response.status_code == 201, response.text
    ride: dict[str, Any] = response.json()
    return ride


async def count_rows(session_factory: SessionFactory, model: type[Base]) -> int:
    async with session_factory() as session, read_transaction(session):
        total = await session.scalar(select(func.count()).select_from(model))
    return total or 0
