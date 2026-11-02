"""MVP_SPEC §9 acceptance: the whole cash ride, only through the public HTTP API.

Admin, passenger and three drivers each have a browser of their own. The route
is the controlled ``FakeRoutingProvider`` (10 km / 25 min -> 2200 KZT); the
background loop is off and the test runs its step after moving the clock.
"""

import uuid
from datetime import timedelta

from fastapi import FastAPI

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import ADMIN_DRIVERS_URL
from support.e2e import (
    Json,
    Participant,
    Town,
    answer,
    create_ride,
    expect,
    expect_error,
    offers,
    only_item,
    open_town,
    pay,
    payment,
    quote,
    ride,
    ride_command,
)
from support.history import ADMIN_RIDES_URL
from support.lifecycle import Event, ride_events
from support.payments import AuditEvent, payment_events
from support.rides import RIDES_URL
from support.routing import FAKE_PROVIDER_NAME, FakeRoutingProvider
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.states import OfferStatus

NEAREST = {"longitude": 76.9580, "latitude": 43.2389}  # ~65 m from the pickup
SECOND = {"longitude": 76.9650, "latitude": 43.2389}  # ~630 m
THIRD = {"longitude": 76.9750, "latitude": 43.2389}  # ~1.4 km
TTL = timedelta(seconds=30)


def summary(page: Json) -> tuple[object, ...]:
    item = only_item(page)
    return item["id"], item["status"], item["payment_status"], item["payment_method"]


async def three_drivers(town: Town) -> tuple[Participant, Participant, Participant]:
    return (
        await town.driver("driver_near", location=NEAREST),
        await town.driver("driver_middle", location=SECOND),
        await town.driver("driver_far", location=THIRD),
    )


async def test_cash_ride_from_registration_to_history(
    app: FastAPI,
    session_factory: SessionFactory,
    clock: ManualClock,
    dispatcher: Dispatcher,
    routing_provider: FakeRoutingProvider,
) -> None:
    async with open_town(app, session_factory, clock) as town:
        admin = await town.admin()
        pat = await town.passenger("pat")
        near, middle, far = await three_drivers(town)
        approved = expect(await admin.get(ADMIN_DRIVERS_URL, approval_status="approved"))
        assert approved["total"] == 3

        # Quote from the road route, then an idempotent order.
        quoted = await quote(pat)
        assert (quoted["amount_kzt"], quoted["currency"]) == (2200, "KZT")
        assert quoted["route"]["provider"] == FAKE_PROVIDER_NAME
        assert routing_provider.call_count == 1
        key = uuid.uuid4().hex
        created = expect(await create_ride(pat, quoted["quote_id"], key), 201)
        replayed = await create_ride(pat, quoted["quote_id"], key)
        assert expect(replayed, 201)["id"] == created["id"]
        assert replayed.headers["Idempotent-Replayed"] == "true"
        ride_id = created["id"]
        assert (created["status"], created["driver_id"], created["amount_kzt"]) == (
            "searching",
            None,
            2200,
        )

        # The nearest driver is asked first and declines; the next one is asked at once.
        [first] = await offers(near)
        assert first["ride_id"] == ride_id
        assert await offers(middle) == await offers(far) == []
        assert expect(await answer(near, first["id"], "reject"))["status"] == "rejected"
        [second] = await offers(middle)

        # The second offer runs out; the loop's step asks the third driver.
        clock.advance(TTL)
        assert await offers(middle) == []
        assert await town.dispatch_step() == 1
        expect_error(await answer(middle, second["id"], "accept"), 409, "offer_expired")
        [third] = await offers(far)
        assert await offers(near) == []  # declined in this search, not asked again
        assigned = expect(await answer(far, third["id"], "accept"))
        assert (assigned["status"], assigned["driver_id"]) == ("assigned", str(far.id))

        card = expect(await ride(pat, ride_id))["driver"]
        assert (card["full_name"], card["vehicle"]["plate_number"]) == ("Dana Driver", "003ETE02")
        expect_error(await ride(near, ride_id), 404, "ride_not_found")
        expect_error(await ride_command(middle, ride_id, "arrive"), 404, "ride_not_found")

        for command, status in (
            ("arrive", "arrived"),
            ("start", "in_progress"),
            ("complete", "completed"),
        ):
            assert expect(await ride_command(far, ride_id, command))["status"] == status
        expect_error(await ride_command(pat, ride_id, "cancel"), 409, "invalid_ride_transition")

        # Cash is open and unpaid; only the driver (or admin) confirms it.
        opened = await payment(pat, ride_id)
        assert {k: opened[k] for k in ("amount_kzt", "method", "status", "verification")} == {
            "amount_kzt": 2200,
            "method": "cash",
            "status": "unpaid",
            "verification": "manual",
        }
        assert opened["kaspi_available"] is False
        expect_error(
            await pay(pat, ride_id, "method", {"method": "kaspi_link"}), 503, "kaspi_unavailable"
        )
        expect_error(await pay(pat, ride_id, "confirm"), 403, "payment_action_forbidden")
        confirmed = expect(await pay(far, ride_id, "confirm"))
        assert (confirmed["status"], confirmed["changed"]) == ("confirmed", True)
        assert expect(await pay(far, ride_id, "confirm"))["changed"] is False

        # History of both sides and the admin list show the paid ride.
        expected = (ride_id, "completed", "confirmed", "cash")
        assert summary(expect(await pat.get(RIDES_URL))) == expected
        assert summary(expect(await far.get(RIDES_URL))) == expected
        assert expect(await near.get(RIDES_URL))["total"] == 0
        assert expect(await middle.get(RIDES_URL))["total"] == 0
        admin_page = expect(await admin.get(ADMIN_RIDES_URL, driver_id=str(far.id)))
        assert summary(admin_page) == expected
        expect_error(await admin.get(RIDES_URL), 403, "forbidden")

    ride_uuid = uuid.UUID(ride_id)
    assert [(o.driver_id, o.status) for o in await dispatcher.offers(ride_uuid)] == [
        (near.id, OfferStatus.REJECTED),
        (middle.id, OfferStatus.EXPIRED),
        (far.id, OfferStatus.ACCEPTED),
    ]
    assert await ride_events(session_factory, ride_uuid) == [
        Event("searching", "assigned", "assign", far.id, None),
        Event("assigned", "arrived", "arrive", far.id, None),
        Event("arrived", "in_progress", "start", far.id, None),
        Event("in_progress", "completed", "complete", far.id, None),
    ]
    assert await payment_events(session_factory, ride_uuid) == [
        AuditEvent("open", None, "unpaid", None, "cash", None, None),
        AuditEvent("confirm", "unpaid", "confirmed", "cash", "cash", far.id, None),
    ]
