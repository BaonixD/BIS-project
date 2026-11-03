"""Dispatch and ride commands lock the ride row before its offers (ADR 0006, 0007).

SQLite ignores FOR UPDATE (writers are serialized by BEGIN IMMEDIATE), so the
executed SELECTs are captured and compiled for PostgreSQL, where the order
rides -> ride_offers keeps concurrent accept, reject and expiry from deadlocking.
"""

import re
from typing import Any

import pytest
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.rides import PICKUP, RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.drivers.exceptions import DriverOnActiveRideError
from taxi_service.modules.rides import lifecycle
from taxi_service.modules.rides.states import OfferStatus, RideCommand
from taxi_service.modules.users.models import UserRole

FROM_TABLE = re.compile(r"\bFROM\s+(\w+)")
POSTGRESQL = PGDialect()  # type: ignore[no-untyped-call]  # SQLAlchemy leaves it untyped


@pytest.fixture
def locking_selects(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Table locked by each SELECT ... FOR UPDATE, in execution order (PostgreSQL SQL)."""
    locked: list[str] = []
    original = AsyncSession.execute

    async def execute(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(statement, Select):
            sql = str(statement.compile(dialect=POSTGRESQL))
            if "FOR UPDATE" in sql:
                match = FROM_TABLE.search(sql)
                assert match is not None, sql
                locked.append(match.group(1))
        return await original(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", execute)
    return locked


@pytest.mark.parametrize("answer", ["accept", "reject"])
async def test_answers_lock_the_ride_then_the_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    locking_selects: list[str],
    answer: str,
) -> None:
    driver = await driver_factory.driver("driver", location=PICKUP)
    ride = await ride_factory.searching_ride()
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    locking_selects.clear()

    await getattr(dispatcher, answer)(offer.id, driver)

    assert locking_selects == ["rides", "ride_offers"]


async def test_a_search_step_locks_the_ride(
    ride_factory: RideFactory, dispatcher: Dispatcher, locking_selects: list[str]
) -> None:
    ride = await ride_factory.searching_ride()
    locking_selects.clear()

    await dispatcher.process(ride.id)

    assert locking_selects == ["rides"]


async def test_cancel_locks_the_ride_before_revoking_its_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    locking_selects: list[str],
) -> None:
    await driver_factory.driver("driver", location=PICKUP)
    ride = await ride_factory.searching_ride()
    await dispatcher.process(ride.id)
    locking_selects.clear()

    async with session_factory() as session:
        await lifecycle.execute_command(
            session,
            ride.id,
            RideCommand.CANCEL,
            user_id=ride.passenger_id,
            role=UserRole.PASSENGER,
            clock=dispatcher.clock,
        )

    assert locking_selects == ["rides"]
    [offer] = await dispatcher.offers(ride.id)
    assert offer.status is OfferStatus.REVOKED


async def test_driver_guard_reads_rides_without_locking_them(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    locking_selects: list[str],
) -> None:
    driver = await driver_factory.driver("driver", location=PICKUP)
    ride = await ride_factory.searching_ride()
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    await dispatcher.accept(offer.id, driver)
    locking_selects.clear()

    with pytest.raises(DriverOnActiveRideError):
        await driver_factory.go_offline(driver)

    # The profile itself is held with FOR NO KEY UPDATE (test_driver_row_locks.py),
    # which this fixture does not list; the active-ride check takes no row lock.
    assert locking_selects == []
