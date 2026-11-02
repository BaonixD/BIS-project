"""Database constraints of ride_offers and of the search fields of rides (MVP_SPEC §6).

Rows are inserted with raw SQL: one pending offer per ride and per driver, one
offer per driver and ride, a status from the offer lifecycle and consistent times.
"""

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from support.rows import (
    IN_30_S,
    NOW,
    insert_driver,
    insert_offer,
    insert_ride,
    insert_user,
)
from taxi_service.database.session import SessionFactory

DECIDED = ["accepted", "rejected", "expired", "revoked"]


async def test_pending_offer_for_a_searching_ride(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)

    await insert_offer(session_factory, ride, await insert_driver(session_factory))


@pytest.mark.parametrize("status", DECIDED)
async def test_decided_offer_statuses(session_factory: SessionFactory, status: str) -> None:
    ride = await insert_ride(session_factory)

    await insert_offer(session_factory, ride, await insert_driver(session_factory), status=status)


async def test_unknown_offer_status_is_rejected(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_offer(
            session_factory, ride, await insert_driver(session_factory), status="maybe"
        )


@pytest.mark.parametrize("expires_at", [NOW, "2026-11-03 08:59:59.000000"])
async def test_offer_expires_after_it_is_created(
    session_factory: SessionFactory, expires_at: str
) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_offer(
            session_factory, ride, await insert_driver(session_factory), expires_at=expires_at
        )


async def test_pending_offer_has_no_response_time(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_offer(
            session_factory, ride, await insert_driver(session_factory), responded_at=IN_30_S
        )


@pytest.mark.parametrize("status", DECIDED)
async def test_decided_offer_has_a_response_time(
    session_factory: SessionFactory, status: str
) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_offer(
            session_factory,
            ride,
            await insert_driver(session_factory),
            status=status,
            responded_at=None,
        )


async def test_one_pending_offer_per_ride(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, await insert_driver(session_factory))

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_offer(session_factory, ride, await insert_driver(session_factory))


async def test_decided_offers_do_not_block_the_next_pending_one(
    session_factory: SessionFactory,
) -> None:
    ride = await insert_ride(session_factory)
    for status in ("rejected", "expired", "revoked"):
        await insert_offer(
            session_factory, ride, await insert_driver(session_factory), status=status
        )

    await insert_offer(session_factory, ride, await insert_driver(session_factory))


async def test_one_pending_offer_per_driver(session_factory: SessionFactory) -> None:
    driver = await insert_driver(session_factory)
    await insert_offer(session_factory, await insert_ride(session_factory), driver)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_offer(session_factory, await insert_ride(session_factory), driver)


async def test_driver_history_does_not_block_a_new_pending_offer(
    session_factory: SessionFactory,
) -> None:
    driver = await insert_driver(session_factory)
    for status in DECIDED:
        await insert_offer(
            session_factory, await insert_ride(session_factory), driver, status=status
        )

    await insert_offer(session_factory, await insert_ride(session_factory), driver)


@pytest.mark.parametrize("first", DECIDED)
async def test_a_driver_gets_at_most_one_offer_per_ride(
    session_factory: SessionFactory, first: str
) -> None:
    ride = await insert_ride(session_factory)
    driver = await insert_driver(session_factory)
    await insert_offer(session_factory, ride, driver, status=first)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_offer(session_factory, ride, driver)


async def test_offer_needs_an_existing_ride(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)
    driver = await insert_driver(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_offer(session_factory, "0" * 32, driver)
    await insert_offer(session_factory, ride, driver)


async def test_offer_goes_to_a_driver_profile(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)
    passenger = await insert_user(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_offer(session_factory, ride, passenger)


# rides: the search window


@pytest.mark.parametrize("column", ["search_started_at", "search_deadline"])
async def test_ride_search_window_is_required(session_factory: SessionFactory, column: str) -> None:
    missing: dict[str, Any] = {column: None}

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_ride(session_factory, **missing)


@pytest.mark.parametrize("deadline", [NOW, "2026-11-03 08:59:00.000000"])
async def test_ride_search_deadline_follows_its_start(
    session_factory: SessionFactory, deadline: str
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_ride(session_factory, search_deadline=deadline)
