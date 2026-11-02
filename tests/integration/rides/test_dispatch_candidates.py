"""Candidates exclude busy and reserved drivers in SQL (MVP_SPEC §6, ADR 0006).

Busy: an accepted active ride (assigned, arrived, in_progress). Reserved: a pending
offer for any ride. In one search (``in_search``) a driver who already had an offer
in that search, or who once accepted the ride (released it since), is skipped.
"""

import uuid
from datetime import UTC, datetime

import pytest

from support.clock import ManualClock
from support.drivers import DriverFactory
from support.rows import insert_driver, insert_offer, insert_ride
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.drivers.candidates import SearchScope, find_nearby_candidates
from taxi_service.modules.geo.schemas import Coordinates

PICKUP = Coordinates(longitude=76.9457, latitude=43.2383)
NEAR = Coordinates(longitude=76.9467, latitude=43.2383)


SEARCH_START = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)  # support.rows.NOW
RESTARTED = datetime(2026, 11, 3, 9, 2, tzinfo=UTC)
RESTARTED_ROW = "2026-11-03 09:02:00.000000"


async def candidate_ids(
    session_factory: SessionFactory,
    clock: ManualClock,
    ride_id: str | None = None,
    search_started_at: datetime = SEARCH_START,
) -> list[uuid.UUID]:
    scope = None if ride_id is None else SearchScope(uuid.UUID(ride_id), search_started_at)
    async with session_factory() as session, read_transaction(session):
        found = await find_nearby_candidates(session, PICKUP, now=clock.now(), in_search=scope)
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

    assert await candidate_ids(session_factory, clock, ride) == [other]
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

    assert await candidate_ids(session_factory, clock, ride) == [driver]


@pytest.mark.parametrize("status", ["rejected", "expired", "revoked"])
async def test_driver_asked_in_an_earlier_search_of_the_ride_is_a_candidate_again(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    driver = await driver_factory.driver("driver", location=NEAR)
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, driver.hex, status=status)

    assert await candidate_ids(session_factory, clock, ride, RESTARTED) == [driver]


async def test_driver_who_released_the_ride_stays_excluded_in_a_new_search(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    released = await driver_factory.driver("released", location=NEAR)
    other = await driver_factory.driver("other", location=NEAR)
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, released.hex, status="accepted")

    assert await candidate_ids(session_factory, clock, ride, RESTARTED) == [other]


async def test_driver_asked_in_the_new_search_is_skipped_again(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    driver = await driver_factory.driver("driver", location=NEAR)
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, driver.hex, status="rejected")
    await insert_offer(
        session_factory,
        ride,
        driver.hex,
        status="rejected",
        created_at=RESTARTED_ROW,
        expires_at="2026-11-03 09:02:30.000000",
        responded_at="2026-11-03 09:02:10.000000",
        search_started_at=RESTARTED_ROW,
    )

    assert await candidate_ids(session_factory, clock, ride, RESTARTED) == []
