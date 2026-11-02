"""MVP_SPEC §6 acceptance through the API: cancellation, release and the end of a search.

Each participant has a browser of their own; the loop is off and its step runs
after the test moves the clock.
"""

import uuid
from datetime import timedelta

from fastapi import FastAPI

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import AVAILABILITY_URL, LOCATION_URL
from support.e2e import (
    answer,
    expect,
    expect_error,
    offers,
    open_town,
    order,
    ride,
    ride_command,
)
from support.lifecycle import Event, commands_of, ride_events
from support.rides import RIDES_URL
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.states import OfferStatus

NEAREST = {"longitude": 76.9580, "latitude": 43.2389}
SECOND = {"longitude": 76.9650, "latitude": 43.2389}
THIRD = {"longitude": 76.9750, "latitude": 43.2389}
TTL = timedelta(seconds=30)


async def test_cancel_while_searching_revokes_the_offer(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock, dispatcher: Dispatcher
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        dana = await town.driver("dana", location=NEAREST)
        ride_id = (await order(pat))["id"]
        [offer] = await offers(dana)

        cancelled = expect(await ride_command(pat, ride_id, "cancel", {"reason": "plans changed"}))
        assert (cancelled["status"], cancelled["cancel_reason"]) == ("cancelled", "plans changed")
        assert await offers(dana) == []
        expect_error(await answer(dana, offer["id"], "accept"), 409, "invalid_ride_transition")
        assert await town.dispatch_step() == 0

        # The passenger may order again; the same driver gets the new ride.
        again = await order(pat)
        [new_offer] = await offers(dana)
        assert new_offer["ride_id"] == again["id"] != ride_id

    assert [o.status for o in await dispatcher.offers(uuid.UUID(ride_id))] == [OfferStatus.REVOKED]
    assert await ride_events(session_factory, uuid.UUID(ride_id)) == [
        Event("searching", "cancelled", "cancel", pat.id, "plans changed")
    ]


async def test_cancel_after_assignment_frees_the_driver_for_another_ride(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        pia = await town.passenger("pia")
        dana = await town.driver("dana", location=NEAREST)
        ride_id = (await order(pat))["id"]
        [offer] = await offers(dana)
        expect(await answer(dana, offer["id"], "accept"))
        expect_error(
            await dana.put(AVAILABILITY_URL, {"online": False}), 409, "driver_on_active_ride"
        )

        assert expect(await ride_command(pat, ride_id, "cancel"))["status"] == "cancelled"
        expect_error(await ride_command(dana, ride_id, "arrive"), 409, "invalid_ride_transition")

        other = await order(pia)
        [next_offer] = await offers(dana)
        assert next_offer["ride_id"] == other["id"]
        assigned = expect(await answer(dana, next_offer["id"], "accept"))
        assert (assigned["status"], assigned["driver_id"]) == ("assigned", str(dana.id))
        cancelled = expect(await ride(pat, ride_id))
        assert (cancelled["status"], cancelled["driver_id"]) == ("cancelled", str(dana.id))

    assert await commands_of(session_factory, uuid.UUID(ride_id)) == ["assign", "cancel"]


async def test_release_starts_a_new_search_without_the_releasing_driver(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock, dispatcher: Dispatcher
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        dana = await town.driver("dana", location=NEAREST)
        dima = await town.driver("dima", location=SECOND)
        ride_id = (await order(pat))["id"]
        [offer] = await offers(dana)
        expect(await answer(dana, offer["id"], "accept"))
        expect(await ride_command(dana, ride_id, "arrive"))

        released = expect(await ride_command(dana, ride_id, "release", {"reason": "flat tyre"}))
        assert (released["status"], released["driver_id"]) == ("searching", None)
        expect_error(await ride(dana, ride_id), 404, "ride_not_found")
        assert await offers(dana) == []
        [retry] = await offers(dima)
        assert retry["ride_id"] == ride_id
        expect(await answer(dima, retry["id"], "accept"))
        for command in ("arrive", "start", "complete"):
            expect(await ride_command(dima, ride_id, command))
        assert expect(await dana.get(RIDES_URL))["total"] == 0
        assert expect(await dima.get(RIDES_URL))["items"][0]["id"] == ride_id

    ride_uuid = uuid.UUID(ride_id)
    assert {o.driver_id: o.status for o in await dispatcher.offers(ride_uuid)} == {
        dana.id: OfferStatus.ACCEPTED,
        dima.id: OfferStatus.ACCEPTED,
    }
    events = await ride_events(session_factory, ride_uuid)
    assert [(e.command, e.actor_id) for e in events] == [
        ("assign", dana.id),
        ("arrive", dana.id),
        ("release", dana.id),
        ("assign", dima.id),
        ("arrive", dima.id),
        ("start", dima.id),
        ("complete", dima.id),
    ]
    assert events[2].reason == "flat tyre"


async def test_no_driver_at_once_without_candidates(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        await town.driver("offline_driver", location=NEAREST, online=False)
        await town.driver("far_driver", location={"longitude": 77.0500, "latitude": 43.2389})

        ended = await order(pat)
        assert ended["status"] == "no_driver"
        retry = await order(pat)  # no_driver is final; a new order is allowed

    assert retry["status"] == "no_driver"
    assert await ride_events(session_factory, uuid.UUID(ended["id"])) == [
        Event("searching", "no_driver", "mark_no_driver", None, None)
    ]


async def test_search_ends_after_its_180_second_budget(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock, dispatcher: Dispatcher
) -> None:
    """The last offer made inside the budget lives its 30 s; then no one else is asked."""
    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        drivers = [
            await town.driver(name, location=place)
            for name, place in (("d_near", NEAREST), ("d_middle", SECOND), ("d_far", THIRD))
        ]
        ride_id = (await order(pat))["id"]

        clock.advance(timedelta(seconds=179))
        for driver, place in zip(drivers, (NEAREST, SECOND, THIRD), strict=True):
            expect(await driver.put(LOCATION_URL, place))  # still fresh candidates
        assert await town.dispatch_step() == 1
        [late] = await offers(drivers[1])

        clock.advance(TTL)  # 209 s: the late offer ran out and so has the budget
        assert await town.dispatch_step() == 1
        ended = expect(await ride(pat, ride_id))
        assert ended["status"] == "no_driver"
        assert await offers(drivers[2]) == []
        expect_error(await answer(drivers[1], late["id"], "accept"), 409, "offer_expired")

    assert [(o.driver_id, o.status) for o in await dispatcher.offers(uuid.UUID(ride_id))] == [
        (drivers[0].id, OfferStatus.EXPIRED),
        (drivers[1].id, OfferStatus.EXPIRED),
    ]
    assert await commands_of(session_factory, uuid.UUID(ride_id)) == ["mark_no_driver"]
