"""Ride payments through the API and the stored ``payments``/``payment_events`` rows.

Usage in an API test with the ``client``, ``driver_factory``, ``dispatcher`` and
``session_factory`` fixtures (``support.lifecycle``: passenger ``pat``, driver ``dana``)::

    trip = await trip_in("completed", client, driver_factory, dispatcher)
    response = await pay(client, trip.ride_id, "confirm", trip.driver)
    assert [event.action for event in await payment_events(session_factory, trip.ride_id)] == [
        "open", "confirm"
    ]

Kaspi is off unless a test uses the ``kaspi_settings`` fixture (``tests/api/payments``);
the link is always the controlled ``TEST_KASPI_URL``, never the owner's real one.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import httpx
from sqlalchemy import literal_column, select

from support.drivers import login_as
from support.rides import ride_url
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.models import Payment, PaymentEvent

TEST_KASPI_URL: Final = "https://pay.kaspi.kz/pay/test123"
ADMIN: Final = "admin"
REFERENCE: Final = "POS receipt 0042"


def kaspi_on() -> PaymentSettings:
    return PaymentSettings(_env_file=None, kaspi_payment_url=TEST_KASPI_URL)


def kaspi_off() -> PaymentSettings:
    return PaymentSettings(_env_file=None, kaspi_payment_url=None)


def payment_url(ride_id: uuid.UUID | str, action: str | None = None) -> str:
    """``/rides/{id}/payment`` or one of its commands: ``method``, ``report``, ``confirm``."""
    base = f"{ride_url(ride_id)}/payment"
    return f"{base}/{action}" if action else base


@dataclass(frozen=True)
class StoredPayment:
    amount_kzt: int
    currency: str
    method: str
    status: str
    verification: str
    reported_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by: uuid.UUID | None
    confirmation_reference: str | None
    created_at: datetime


@dataclass(frozen=True)
class AuditEvent:
    action: str
    from_status: str | None
    to_status: str
    from_method: str | None
    to_method: str
    actor_id: uuid.UUID | None
    reference: str | None


async def read_payment(client: httpx.AsyncClient, ride_id: uuid.UUID, username: str) -> Any:
    """``GET /rides/{id}/payment`` as ``username``; must answer 200."""
    await login_as(client, username)
    response = await client.get(payment_url(ride_id))
    assert response.status_code == 200, response.text
    return response.json()


async def pay(
    client: httpx.AsyncClient,
    ride_id: uuid.UUID | str,
    action: str,
    username: str,
    *,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    """Log in as ``username`` and send a payment command.

    ``method`` is a PUT (body ``{"method": ...}`` required); ``report`` and
    ``confirm`` are POSTs with an optional body.
    """
    user = await login_as(client, username)
    url = payment_url(ride_id, action)
    if action == "method":
        return await client.put(url, json=json, headers=user.csrf_headers)
    return await client.post(url, json=json, headers=user.csrf_headers)


async def expect_paid_ok(
    client: httpx.AsyncClient,
    ride_id: uuid.UUID,
    action: str,
    username: str,
    *,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await pay(client, ride_id, action, username, json=json)
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
        verification=row.verification.value,
        reported_at=row.reported_at,
        confirmed_at=row.confirmed_at,
        confirmed_by=row.confirmed_by,
        confirmation_reference=row.confirmation_reference,
        created_at=row.created_at,
    )


async def payment_events(session_factory: SessionFactory, ride_id: uuid.UUID) -> list[AuditEvent]:
    """The payment's audit history, oldest first (``rowid`` breaks ties of a still clock)."""
    query = (
        select(PaymentEvent)
        .join(Payment, Payment.id == PaymentEvent.payment_id)
        .where(Payment.ride_id == ride_id)
        .order_by(PaymentEvent.created_at, literal_column("payment_events.rowid"))
    )
    async with session_factory() as session, read_transaction(session):
        rows = list(await session.scalars(query))
    return [
        AuditEvent(
            action=row.action.value,
            from_status=None if row.from_status is None else row.from_status.value,
            to_status=row.to_status.value,
            from_method=None if row.from_method is None else row.from_method.value,
            to_method=row.to_method.value,
            actor_id=row.actor_id,
            reference=row.reference,
        )
        for row in rows
    ]


async def actions_of(session_factory: SessionFactory, ride_id: uuid.UUID) -> list[str]:
    return [event.action for event in await payment_events(session_factory, ride_id)]
