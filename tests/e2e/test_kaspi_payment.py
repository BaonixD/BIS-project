"""MVP_SPEC §7 acceptance through the API: Kaspi by the controlled link, confirmed only by admin.

The link is ``TEST_KASPI_URL`` (``support.payments``), never the owner's real
one; no request leaves the test process and no payment is made.
"""

import uuid

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
from support.payments import REFERENCE, TEST_KASPI_URL, AuditEvent, kaspi_on, payment_events
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


async def test_kaspi_report_is_not_payment_until_admin_confirms(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        admin = await town.admin()
        ride_id, pat, dana = await completed_ride(town)
        cash = await payment(pat, ride_id)
        assert (cash["method"], cash["kaspi_available"], cash["payment_url"]) == (
            "cash",
            True,
            None,
        )

        switched = expect(await pay(pat, ride_id, "method", KASPI))
        assert (switched["method"], switched["status"]) == ("kaspi_link", "unpaid")
        assert switched["payment_url"] == TEST_KASPI_URL
        assert switched["amount_entered_by_buyer"] is True

        reported = expect(await pay(pat, ride_id, "report"))
        assert (reported["status"], reported["confirmed_at"]) == ("reported", None)
        assert expect(await pay(pat, ride_id, "report"))["changed"] is False
        expect_error(await pay(dana, ride_id, "confirm"), 403, "payment_action_forbidden")
        expect_error(await pay(admin, ride_id, "confirm"), 422, "confirmation_reference_required")
        history = only_item(expect(await pat.get(RIDES_URL)))
        assert (history["payment_status"], history["payment_method"]) == ("reported", "kaspi_link")
        assert (await payment(dana, ride_id))["status"] == "reported"

        confirmed = expect(await pay(admin, ride_id, "confirm", {"reference": REFERENCE}))
        assert (confirmed["status"], confirmed["verification"]) == ("confirmed", "manual")
        assert confirmed["confirmation_reference"] == REFERENCE
        assert confirmed["payment_url"] is None
        seen_by_passenger = await payment(pat, ride_id)
        assert (seen_by_passenger["status"], seen_by_passenger["confirmation_reference"]) == (
            "confirmed",
            None,
        )
        expect_error(
            await pay(pat, ride_id, "method", {"method": "cash"}), 409, "invalid_payment_transition"
        )
        listed = only_item(expect(await admin.get(ADMIN_RIDES_URL, status="completed")))
        assert (listed["payment_status"], listed["payment_method"]) == ("confirmed", "kaspi_link")

    assert await payment_events(session_factory, uuid.UUID(ride_id)) == [
        AuditEvent("open", None, "unpaid", None, "cash", None, None),
        AuditEvent("change_method", "unpaid", "unpaid", "cash", "kaspi_link", pat.id, None),
        AuditEvent("report", "unpaid", "reported", "kaspi_link", "kaspi_link", pat.id, None),
        AuditEvent(
            "confirm", "reported", "confirmed", "kaspi_link", "kaspi_link", admin.id, REFERENCE
        ),
    ]
