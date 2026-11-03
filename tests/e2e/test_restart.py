"""MVP_SPEC §6 "Перезапуск и гонки": the search and unpaid rides survive an application restart.

The first application runs without the background loop and is stopped while an
offer is pending; the clock passes its deadline while nothing runs. A new
application on the same database file then runs the loop every 10 ms (the only
test here with a running loop, for at most a few seconds). Sessions live in the
database, so participants keep their cookies across the restart.
"""

import asyncio
import uuid
from datetime import timedelta
from typing import Any

from fastapi import FastAPI

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.e2e import (
    Participant,
    Town,
    answer,
    eventually,
    expect,
    expect_error,
    offers,
    open_town,
    order,
    pay,
    payment,
    ride,
    ride_command,
)
from support.lifecycle import commands_of
from support.payments import kaspi_off
from support.routing import FakeRoutingProvider
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory
from taxi_service.main import create_app
from taxi_service.modules.rides.states import OfferStatus

NEAREST = {"longitude": 76.9580, "latitude": 43.2389}
SECOND = {"longitude": 76.9650, "latitude": 43.2389}
THIRD = {"longitude": 76.9750, "latitude": 43.2389}
TTL = timedelta(seconds=30)
LOOP = {"dispatch_loop_enabled": True, "dispatch_interval_s": 0.01}


def restarted(settings: Settings, clock: ManualClock, **changes: Any) -> FastAPI:
    """A new application on the same database file and clock."""
    return create_app(
        settings.model_copy(update=changes),
        clock=clock,
        routing_provider=FakeRoutingProvider(),
        payment_settings=kaspi_off(),
    )


async def started_ride(passenger: Participant, driver: Participant) -> str:
    """The passenger's new ride, accepted by ``driver`` (the nearest free one) and started."""
    ride_id: str = (await order(passenger))["id"]
    [offer] = await offers(driver)
    expect(await answer(driver, offer["id"], "accept"))
    for command in ("arrive", "start"):
        expect(await ride_command(driver, ride_id, command))
    return ride_id


async def reconnect_all(town: Town, *participants: Participant) -> list[Participant]:
    return [await town.reconnect(participant) for participant in participants]


async def test_restart_after_the_offer_deadline_moves_on_without_double_assignment(
    app: FastAPI,
    settings: Settings,
    session_factory: SessionFactory,
    clock: ManualClock,
    dispatcher: Dispatcher,
) -> None:
    async with open_town(app, session_factory, clock) as before:
        pat, pia, sam = [await before.passenger(name) for name in ("pat", "pia", "sam")]
        dora = await before.driver("dora", location=THIRD)
        trip = await started_ride(sam, dora)  # in progress across the restart
        dana = await before.driver("dana", location=NEAREST)
        dima = await before.driver("dima", location=SECOND)
        unpaid_ride = await started_ride(pia, dana)
        expect(await ride_command(dana, unpaid_ride, "complete"))
        ride_id = (await order(pat))["id"]
        [stale] = await offers(dana)
    clock.advance(TTL)  # the offer runs out while the application is down
    ride_uuid = uuid.UUID(ride_id)
    assert [o.status for o in await dispatcher.offers(ride_uuid)] == [OfferStatus.PENDING]

    app_after = restarted(settings, clock, **LOOP)
    async with open_town(app_after, session_factory, clock) as after:
        pat, pia, sam, dana, dima, dora = await reconnect_all(
            after, pat, pia, sam, dana, dima, dora
        )
        assert app_after.state.dispatch_loop.running

        async def moved_on() -> bool:
            return {o.driver_id: o.status for o in await dispatcher.offers(ride_uuid)} == {
                dana.id: OfferStatus.EXPIRED,
                dima.id: OfferStatus.PENDING,
            }

        await eventually(moved_on)
        expect_error(await answer(dana, stale["id"], "accept"), 409, "offer_expired")
        [fresh] = await offers(dima)
        assert await offers(dora) == []
        assigned = expect(await answer(dima, fresh["id"], "accept"))
        await asyncio.sleep(0.05)  # several more loop passes over the assigned ride
        assert (
            expect(await ride(pat, ride_id))["driver_id"] == str(dima.id) == assigned["driver_id"]
        )

        # The unpaid ride from before the restart is still open and can be settled.
        left_open = await payment(pia, unpaid_ride)
        assert (left_open["status"], left_open["amount_kzt"]) == ("unpaid", 2200)
        assert expect(await pay(dana, unpaid_ride, "confirm"))["status"] == "confirmed"
        # The ride in progress goes on with its driver and is paid after completion.
        assert expect(await ride(sam, trip))["status"] == "in_progress"
        expect(await ride_command(dora, trip, "complete"))
        assert expect(await pay(dora, trip, "confirm"))["status"] == "confirmed"

    assert {o.driver_id: o.status for o in await dispatcher.offers(ride_uuid)} == {
        dana.id: OfferStatus.EXPIRED,
        dima.id: OfferStatus.ACCEPTED,
    }
    assert await commands_of(session_factory, ride_uuid) == ["assign"]
    assert await commands_of(session_factory, uuid.UUID(trip)) == [
        "assign",
        "arrive",
        "start",
        "complete",
    ]


async def test_two_applications_on_one_database_make_one_next_offer(
    app: FastAPI,
    settings: Settings,
    session_factory: SessionFactory,
    clock: ManualClock,
    dispatcher: Dispatcher,
) -> None:
    async with open_town(app, session_factory, clock) as first:
        pat = await first.passenger("pat")
        dana = await first.driver("dana", location=NEAREST)
        dima = await first.driver("dima", location=SECOND)
        await first.driver("dora", location=THIRD)
        ride_id = (await order(pat))["id"]
        async with open_town(restarted(settings, clock), session_factory, clock) as second:
            dima_elsewhere = await second.reconnect(dima)
            clock.advance(TTL)

            passes = await asyncio.gather(first.dispatch_step(), second.dispatch_step())

            assert sorted(passes) in ([0, 1], [1, 1])
            [offer] = await offers(dima_elsewhere)
            accepted = await asyncio.gather(
                answer(dima, offer["id"], "accept"), answer(dima_elsewhere, offer["id"], "accept")
            )
            assert [response.status_code for response in accepted] == [200, 200]

    statuses = [o.status for o in await dispatcher.offers(uuid.UUID(ride_id))]
    assert sorted(statuses) == [OfferStatus.ACCEPTED, OfferStatus.EXPIRED]
    ride_row = await dispatcher.ride(uuid.UUID(ride_id))
    assert ride_row.driver_id == dima.id
    assert (await dispatcher.offers(driver_id=dana.id))[0].status is OfferStatus.EXPIRED
    assert await commands_of(session_factory, uuid.UUID(ride_id)) == ["assign"]
