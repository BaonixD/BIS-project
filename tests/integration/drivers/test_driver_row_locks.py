"""Driver write paths read the profile row with FOR UPDATE.

SQLite ignores the clause (writes are serialized by BEGIN IMMEDIATE), so the
executed statements are captured and compiled for PostgreSQL, where the lock
keeps approval and a concurrent profile edit from both acting on stale data.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from support.clock import ManualClock
from support.drivers import DriverFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.drivers import service as driver_service
from taxi_service.modules.drivers.schemas import DriverProfileUpdate
from taxi_service.modules.drivers.service import DriverAdminService
from taxi_service.modules.geo.schemas import Coordinates

WriteCommand = Callable[[AsyncSession, ManualClock, uuid.UUID, uuid.UUID], Awaitable[object]]
POSTGRESQL = PGDialect()  # type: ignore[no-untyped-call]  # SQLAlchemy leaves it untyped


async def edit_profile(
    session: AsyncSession, clock: ManualClock, driver: uuid.UUID, _: Any
) -> object:
    update = DriverProfileUpdate(full_name="New Name")
    return await driver_service.update_profile(session, driver, update, clock=clock)


async def go_offline(
    session: AsyncSession, clock: ManualClock, driver: uuid.UUID, _: Any
) -> object:
    return await driver_service.set_availability(session, driver, False, clock=clock)


async def move(session: AsyncSession, clock: ManualClock, driver: uuid.UUID, _: Any) -> object:
    point = Coordinates(longitude=76.95, latitude=43.24)
    return await driver_service.update_location(session, driver, point, clock=clock)


async def approve(
    session: AsyncSession, clock: ManualClock, driver: uuid.UUID, admin: uuid.UUID
) -> object:
    return await DriverAdminService(session, clock).approve(driver, admin_id=admin)


@pytest.fixture
def driver_profile_selects(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """SELECTs on driver_profiles executed through AsyncSession, compiled for PostgreSQL."""
    compiled: list[str] = []
    original = AsyncSession.execute

    async def execute(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(statement, Select):
            sql = str(statement.compile(dialect=POSTGRESQL))
            if "FROM driver_profiles" in sql:
                compiled.append(sql)
        return await original(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", execute)
    return compiled


@pytest.mark.parametrize("command", [edit_profile, go_offline, move, approve])
async def test_write_paths_lock_the_driver_profile(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    driver_profile_selects: list[str],
    command: WriteCommand,
) -> None:
    driver = await driver_factory.driver("dana", approved=False)
    admin = await driver_factory.admin_id()
    driver_profile_selects.clear()

    async with session_factory() as session:
        await command(session, clock, driver, admin)

    assert driver_profile_selects, "the profile must be read with a locking SELECT"
    for sql in driver_profile_selects:
        # NO KEY: the row is never re-keyed, and the FK checks of offers and rides
        # (FOR KEY SHARE) must not wait for it (ADR 0006, lock order).
        assert "FOR NO KEY UPDATE OF driver_profiles" in sql
