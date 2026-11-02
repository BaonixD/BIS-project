"""Candidates exclude busy and reserved drivers in SQL (MVP_SPEC §6, ADR 0006).

Busy: an accepted active ride (assigned, arrived, in_progress). Reserved: a pending
offer for any ride. In one search (``for_ride_id``) a driver who already had any
offer for that ride is never a candidate again.
"""

import uuid

import pytest

from support.clock import ManualClock
from support.drivers import DriverFactory
from support.rows import insert_driver, insert_offer, insert_ride
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.drivers.candidates import find_nearby_candidates
from taxi_service.modules.geo.schemas import Coordinates

PICKUP = Coordinates(longitude=76.9457, latitude=43.2383)
NEAR = Coordinates(longitude=76.9467, latitude=43.2383)


async def candidate_ids(
    session_factory: SessionFactory, clock: ManualClock, for_ride_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    async with session_factory() as session, read_transaction(session):
        found = await find_nearby_candidates(
            session, PICKUP, now=clock.now(), for_ride_id=for_ride_id
        )
    return [candidate.driver_id for candidate in found]


@pytest.mark.parametrize("status", ["assigned", "arrived", "in_progress"])
async def test_driver_with_an_accepted_active_ride_is_busy(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    busy = await driver_factory.driver("busy", location=NEAR)
    free = await driver_factory.driver("free", location=NEAR)
    await insert_ride(session_factory, status=status, driver_id=busy.hex)

    assert await candidate_ids(session_factory, clock) == [free]


@pytest.mark.parametrize("status", ["completed", "cancelled"])
async def test_finished_rides_do_not_make_a_driver_busy(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    driver = await driver_factory.driver("driver", location=NEAR)
    await insert_ride(session_factory, status=status, driver_id=driver.hex)

    assert await candidate_ids(session_factory, clock) == [driver]


async def test_driver_with_a_pending_offer_is_reserved(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    reserved = await driver_factory.driver("reserved", location=NEAR)
    free = await driver_factory.driver("free", location=NEAR)
    await insert_offer(session_factory, await insert_ride(session_factory), reserved.hex)

    assert await candidate_ids(session_factory, clock) == [free]


@pytest.mark.parametrize("status", ["rejected", "expired", "revoked"])
async def test_decided_offers_elsewhere_do_not_reserve_a_driver(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    driver = await driver_factory.driver("driver", location=NEAR)
    await insert_offer(
        session_factory, await insert_ride(session_factory), driver.hex, status=status
    )

    assert await candidate_ids(session_factory, clock) == [driver]


@pytest.mark.parametrize("status", ["rejected", "expired", "revoked", "accepted"])
async def test_driver_already_asked_in_this_search_is_skipped(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    asked = await driver_factory.driver("asked", location=NEAR)
    other = await driver_factory.driver("other", location=NEAR)
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, asked.hex, status=status)

    assert await candidate_ids(session_factory, clock, uuid.UUID(ride)) == [other]
    assert set(await candidate_ids(session_factory, clock)) == {asked, other}


async def test_offers_for_other_rides_do_not_exclude_from_this_search(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    driver = await driver_factory.driver("driver", location=NEAR)
    other_ride = await insert_ride(session_factory)
    await insert_offer(session_factory, other_ride, driver.hex, status="rejected")
    await insert_offer(
        session_factory, other_ride, await insert_driver(session_factory), status="expired"
    )
    ride = await insert_ride(session_factory)

    assert await candidate_ids(session_factory, clock, uuid.UUID(ride)) == [driver]
