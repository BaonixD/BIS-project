"""Write paths must survive conflicts that SQLite's serialized writes would hide.

On PostgreSQL two transactions can pass the same Python pre-check; the
database constraint then decides. These tests force that situation by
making the pre-check or the first lookup miss.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select

from support.clock import ManualClock
from support.drivers import DriverFactory, vehicle
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.drivers.exceptions import PlateNumberTakenError
from taxi_service.modules.drivers.models import Vehicle
from taxi_service.modules.drivers.repository import DriverRepository
from taxi_service.modules.drivers.schemas import DriverProfileUpdate
from taxi_service.modules.drivers.service import DriverService
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.users.repository import UserRepository
from taxi_service.modules.users.schemas import MyProfileUpdate
from taxi_service.modules.users.service import UserService

POINT = Coordinates(longitude=76.9457, latitude=43.2383)


def missing_once(original: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a repository lookup so that its first call reports "no row yet"."""
    calls = 0

    async def lookup(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return await original(self, *args, **kwargs)

    return lookup


async def plates(session_factory: SessionFactory) -> list[str]:
    async with session_factory() as session, read_transaction(session):
        return list(
            await session.scalars(select(Vehicle.plate_number).order_by(Vehicle.plate_number))
        )


async def test_plate_constraint_violation_is_reported_as_taken(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await driver_factory.driver("first")  # plate 001TST02
    second = await driver_factory.driver("second", approved=False)  # plate 002TST02

    async def plate_is_free(*_args: Any, **_kwargs: Any) -> bool:
        return False  # a concurrent transaction took it after this check

    monkeypatch.setattr(DriverRepository, "plate_number_taken", plate_is_free)
    update = DriverProfileUpdate.model_validate({"vehicle": vehicle("001TST02")})

    async with session_factory() as session:
        with pytest.raises(PlateNumberTakenError):
            await DriverService(session, clock).update_profile(second, update)

    assert await plates(session_factory) == ["001TST02", "002TST02"]


async def test_concurrent_first_driver_write_uses_the_existing_row(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = await driver_factory.driver("dana", approved=False)
    monkeypatch.setattr(
        DriverRepository, "get_for_update", missing_once(DriverRepository.get_for_update)
    )

    async with session_factory() as session:
        profile = await DriverService(session, clock).update_location(driver, POINT)

    assert (profile.longitude, profile.latitude) == (POINT.longitude, POINT.latitude)
    assert profile.full_name == "Dana Driver"  # the existing row, not a new empty one


async def test_concurrent_first_profile_write_uses_the_existing_row(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await driver_factory.admin_id()
    async with session_factory() as session:
        users = UserService(session, clock, driver_factory.hasher)
        await users.update_profile(user_id, MyProfileUpdate(display_name="Root"))
    monkeypatch.setattr(UserRepository, "get_profile", missing_once(UserRepository.get_profile))

    async with session_factory() as session:
        users = UserService(session, clock, driver_factory.hasher)
        profile = await users.update_profile(user_id, MyProfileUpdate(phone="+77011234567"))

    assert (profile.display_name, profile.phone) == ("Root", "+77011234567")


async def test_first_write_for_a_missing_user_still_fails(
    session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with session_factory() as session:
        with pytest.raises(Exception, match="FOREIGN KEY"):
            await DriverService(session, clock).update_location(uuid.uuid4(), POINT)
