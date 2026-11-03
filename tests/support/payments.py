"""Ride payments through the API and the stored ``payments`` row.

Usage in an API test with the ``client``, ``driver_factory``, ``dispatcher`` and
``session_factory`` fixtures (``support.lifecycle``: passenger ``pat``, driver ``dana``)::

    trip = await trip_in("completed", client, driver_factory, dispatcher)
    body = await expect_cash_received(client, trip.ride_id, trip.driver)
    assert (await stored_payment(session_factory, trip.ride_id)).status == "paid"

The method is chosen with the order (``trip_in(..., payment_method="kaspi_link")``).
Kaspi is off unless a test overrides the ``payment_settings`` fixture with ``kaspi_on()``;
the link is always the controlled ``TEST_KASPI_URL``, never the owner's real one, and
a Kaspi order is only a simulated charge.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import httpx
import pytest
from sqlalchemy import select

from support.drivers import login_as
from support.rides import ride_url
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.models import Payment

TEST_KASPI_URL: Final = "https://pay.kaspi.kz/pay/test123"
ADMIN: Final = "admin"


def isolate_payment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner's ``KASPI_PAYMENT_URL`` from a shell or local ``.env`` never reaches a test."""
    # An empty variable outranks the link in a developer's local .env file.
    monkeypatch.setenv("KASPI_PAYMENT_URL", "")


def kaspi_on() -> PaymentSettings:
    return PaymentSettings(_env_file=None, kaspi_payment_url=TEST_KASPI_URL)


def kaspi_off() -> PaymentSettings:
    return PaymentSettings(_env_file=None, kaspi_payment_url=None)


def payment_url(ride_id: uuid.UUID | str, action: str | None = None) -> str:
    """``/rides/{id}/payment`` or its command ``cash-received``."""
    base = f"{ride_url(ride_id)}/payment"
    return f"{base}/{action}" if action else base


@dataclass(frozen=True)
class StoredPayment:
    amount_kzt: int
    currency: str
    method: str
    status: str
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime
    updated_at: datetime


async def read_payment(client: httpx.AsyncClient, ride_id: uuid.UUID, username: str) -> Any:
    """``GET /rides/{id}/payment`` as ``username``; must answer 200."""
    await login_as(client, username)
    response = await client.get(payment_url(ride_id))
    assert response.status_code == 200, response.text
    return response.json()


async def cash_received(
    client: httpx.AsyncClient,
    ride_id: uuid.UUID | str,
    username: str,
    *,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    """Log in as ``username`` and POST ``cash-received``."""
    user = await login_as(client, username)
    return await client.post(
        payment_url(ride_id, "cash-received"), json=json, headers=user.csrf_headers
    )


async def expect_cash_received(
    client: httpx.AsyncClient, ride_id: uuid.UUID, username: str
) -> dict[str, Any]:
    response = await cash_received(client, ride_id, username)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def stored_payment(
    session_factory: SessionFactory, ride_id: uuid.UUID
) -> StoredPayment | None:
    async with session_factory() as session, read_transaction(session):
        row = await session.scalar(select(Payment).where(Payment.ride_id == ride_id))
    if row is None:
        return None
    return StoredPayment(
        amount_kzt=row.amount_kzt,
        currency=row.currency,
        method=row.method.value,
        status=row.status.value,
        paid_at=row.paid_at,
        refunded_at=row.refunded_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
