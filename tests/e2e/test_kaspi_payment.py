"""MVP_SPEC §7 acceptance through the API: Kaspi chosen before the order (ADR 0010).

The link is ``TEST_KASPI_URL`` (``support.payments``), never the owner's real
one; no request leaves the test process and no payment is made. ``paid`` here is
only a simulated charge when a driver accepts, ``refunded`` a simulated refund.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI

from support.clock import ManualClock
from support.e2e import (
    answer,
    cash_received,
    expect,
    expect_error,
    offers,
    only_item,
    open_town,
    order,
    payment,
    ride_command,
)
from support.history import ADMIN_RIDES_URL
from support.payments import TEST_KASPI_URL, kaspi_on, stored_payment
from support.rides import RIDES_URL
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.config import PaymentSettings

NEAREST = {"longitude": 76.9580, "latitude": 43.2389}
KASPI = "kaspi_link"


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


def at(body: dict[str, object], field: str) -> datetime:
    value = body[field]
    assert isinstance(value, str)
    return datetime.fromisoformat(value)


async def test_kaspi_ride_is_paid_when_a_driver_accepts_and_stays_paid(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        admin = await town.admin()
        pat = await town.passenger("pat")
        dana = await town.driver("dana", location=NEAREST)

        created = await order(pat, KASPI)
        ride_id = created["id"]
        assert (created["payment_method"], created["payment_status"]) == (KASPI, "unpaid")
        waiting = await payment(pat, ride_id)
        assert (waiting["status"], waiting["paid_at"], waiting["payment_url"]) == (
            "unpaid",
            None,
            TEST_KASPI_URL,
        )

        [offer] = await offers(dana)
        clock.advance(timedelta(seconds=10))
        accepted = expect(await answer(dana, offer["id"], "accept"))
        assert accepted["payment_status"] == "paid"
        paid = await payment(pat, ride_id)
        assert (paid["method"], paid["status"]) == (KASPI, "paid")
        assert at(paid, "paid_at") == clock.now()
        clock.advance(timedelta(minutes=20))
        for command in ("arrive", "start", "complete"):
            expect(await ride_command(dana, ride_id, command))
        assert await payment(dana, ride_id) == paid
        expect_error(await cash_received(dana, ride_id), 409, "invalid_payment_transition")

        history = only_item(expect(await pat.get(RIDES_URL)))
        assert (history["payment_status"], history["payment_method"]) == ("paid", KASPI)
        listed = only_item(expect(await admin.get(ADMIN_RIDES_URL, status="completed")))
        assert (listed["payment_status"], listed["payment_method"]) == ("paid", KASPI)


async def test_cancelled_kaspi_ride_is_refunded(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        dana = await town.driver("dana", location=NEAREST)
        ride_id = (await order(pat, KASPI))["id"]
        [offer] = await offers(dana)
        expect(await answer(dana, offer["id"], "accept"))
        paid_at = at(await payment(pat, ride_id), "paid_at")
        clock.advance(timedelta(minutes=2))

        cancelled = expect(await ride_command(pat, ride_id, "cancel"))

        assert (cancelled["status"], cancelled["payment_status"]) == ("cancelled", "refunded")
        refunded = await payment(dana, ride_id)
        assert (refunded["status"], refunded["method"]) == ("refunded", KASPI)
        assert (at(refunded, "paid_at"), at(refunded, "refunded_at")) == (paid_at, clock.now())
        history = only_item(expect(await pat.get(RIDES_URL)))
        assert (history["status"], history["payment_status"]) == ("cancelled", "refunded")

    stored = await stored_payment(session_factory, uuid.UUID(ride_id))
    assert stored is not None
    assert (stored.status, stored.paid_at, stored.refunded_at) == (
        "refunded",
        paid_at,
        clock.now(),
    )


async def test_kaspi_ride_without_drivers_is_never_charged(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")

        created = await order(pat, KASPI)

        assert (created["status"], created["payment_status"]) == ("no_driver", "unpaid")
        assert (await payment(pat, created["id"]))["paid_at"] is None
