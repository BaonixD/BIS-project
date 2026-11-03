"""MVP_SPEC §7 acceptance through the API: Kaspi by the controlled link, paid on "Paid".

The link is ``TEST_KASPI_URL`` (``support.payments``), never the owner's real
one; no request leaves the test process and no payment is made.
"""

import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI

from support.clock import ManualClock
from support.e2e import (
    Participant,
    Town,
    answer,
    expect,
    expect_error,
    offers,
    only_item,
    open_town,
    order,
    pay,
    payment,
    ride_command,
)
from support.history import ADMIN_RIDES_URL
from support.payments import TEST_KASPI_URL, kaspi_on, stored_payment
from support.rides import RIDES_URL
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.config import PaymentSettings

NEAREST = {"longitude": 76.9580, "latitude": 43.2389}
KASPI = {"method": "kaspi_link"}


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


async def completed_ride(town: Town) -> tuple[str, Participant, Participant]:
    pat = await town.passenger("pat")
    dana = await town.driver("dana", location=NEAREST)
    ride_id = (await order(pat))["id"]
    [offer] = await offers(dana)
    expect(await answer(dana, offer["id"], "accept"))
    for command in ("arrive", "start", "complete"):
        expect(await ride_command(dana, ride_id, command))
    return ride_id, pat, dana


async def test_passenger_pays_by_kaspi_link_and_it_counts(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        admin = await town.admin()
        ride_id, pat, dana = await completed_ride(town)
        cash = await payment(pat, ride_id)
        assert (cash["method"], cash["status"], cash["payment_url"]) == ("cash", "unpaid", None)

        switched = expect(await pay(pat, ride_id, "method", KASPI))
        assert (switched["method"], switched["status"]) == ("kaspi_link", "unpaid")
        assert switched["payment_url"] == TEST_KASPI_URL
        assert (await payment(pat, ride_id))["payment_url"] == TEST_KASPI_URL
        expect_error(await pay(dana, ride_id, "pay"), 403, "payment_action_forbidden")
        expect_error(await pay(admin, ride_id, "pay"), 403, "payment_action_forbidden")

        paid = expect(await pay(pat, ride_id, "pay"))
        assert (paid["method"], paid["status"]) == ("kaspi_link", "paid")
        assert datetime.fromisoformat(paid["paid_at"]) == clock.now()
        assert expect(await pay(pat, ride_id, "pay")) == paid
        assert (await payment(dana, ride_id))["status"] == "paid"
        expect_error(
            await pay(pat, ride_id, "method", {"method": "cash"}), 409, "invalid_payment_transition"
        )
        history = only_item(expect(await pat.get(RIDES_URL)))
        assert (history["payment_status"], history["payment_method"]) == ("paid", "kaspi_link")
        listed = only_item(expect(await admin.get(ADMIN_RIDES_URL, status="completed")))
        assert (listed["payment_status"], listed["payment_method"]) == ("paid", "kaspi_link")

    stored = await stored_payment(session_factory, uuid.UUID(ride_id))
    assert stored is not None
    assert (stored.method, stored.status, stored.paid_at) == ("kaspi_link", "paid", clock.now())
