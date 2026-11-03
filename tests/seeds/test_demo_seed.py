"""Demo seed against this test's migrated database, run in-process with the test clock."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from support.clock import ManualClock
from support.drivers import DriverFactory
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.drivers.candidates import find_nearby_candidates
from taxi_service.modules.drivers.models import ApprovalStatus, DriverProfile, Vehicle
from taxi_service.modules.drivers.schemas import DriverProfileUpdate
from taxi_service.modules.drivers.service import DriverService
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.users.models import User, UserProfile, UserRole
from taxi_service.modules.users.schemas import MyProfileUpdate
from taxi_service.modules.users.service import UserService
from taxi_service.seeds.demo import (
    DEMO_ADMIN,
    DEMO_DRIVERS,
    DEMO_PASSENGERS,
    DEMO_PICKUP,
    DEMO_USERNAMES,
    DemoSeedConflictError,
    SeedReport,
    apply_demo_seed,
    plan_demo_seed,
    seed_demo,
)

DEMO_PASSWORD = "demo-passphrase-123"
COUNTED_TABLES = (User, UserProfile, DriverProfile, Vehicle)


@pytest.fixture
def hasher(settings: Settings) -> PasswordHasher:
    return PasswordHasher.from_settings(settings)


async def run_seed(
    session_factory: SessionFactory,
    clock: ManualClock,
    hasher: PasswordHasher,
    *,
    refresh_locations: bool = False,
) -> SeedReport:
    return await seed_demo(
        session_factory,
        clock=clock,
        hasher=hasher,
        password=DEMO_PASSWORD,
        refresh_locations=refresh_locations,
    )


async def users_by_name(session_factory: SessionFactory) -> dict[str, User]:
    async with session_factory() as session, read_transaction(session):
        return {user.username: user for user in await session.scalars(select(User))}


async def driver_profile(session_factory: SessionFactory, username: str) -> DriverProfile:
    user = (await users_by_name(session_factory))[username]
    async with session_factory() as session:
        profile = await DriverService(session, ManualClock()).get(user.id)
    assert profile is not None
    return profile


async def row_counts(session_factory: SessionFactory) -> dict[str, int]:
    async with session_factory() as session, read_transaction(session):
        return {
            model.__tablename__: await session.scalar(select(func.count()).select_from(model)) or 0
            for model in COUNTED_TABLES
        }


async def nearby_driver_ids(session_factory: SessionFactory, clock: ManualClock) -> list[uuid.UUID]:
    async with session_factory() as session, read_transaction(session):
        candidates = await find_nearby_candidates(session, DEMO_PICKUP, now=clock.now())
    return [candidate.driver_id for candidate in candidates]


def entry_for(report: SeedReport, username: str) -> str:
    [entry] = [entry for entry in report.entries if entry.username == username]
    return f"{entry.action} {entry.detail}"


async def test_first_run_creates_the_demo_accounts(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    report = await run_seed(session_factory, clock, hasher)

    assert (report.count("created"), report.count("skipped")) == (6, 0)
    users = await users_by_name(session_factory)
    assert {name: user.role for name, user in users.items()} == {
        DEMO_ADMIN: UserRole.ADMIN,
        "demo_passenger_1": UserRole.PASSENGER,
        "demo_passenger_2": UserRole.PASSENGER,
        "demo_driver_1": UserRole.DRIVER,
        "demo_driver_2": UserRole.DRIVER,
        "demo_driver_3": UserRole.DRIVER,
    }
    assert all(user.password_hash.startswith("$argon2id$") for user in users.values())
    assert await hasher.verify(users["demo_passenger_1"].password_hash, DEMO_PASSWORD)
    async with session_factory() as session:
        profile = await UserService(session, clock, hasher).get_profile(
            users["demo_passenger_2"].id
        )
    assert profile is not None
    assert profile.display_name == "Demo Passenger 2"


async def test_demo_drivers_are_complete_approved_and_online(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)

    admin_id = (await users_by_name(session_factory))[DEMO_ADMIN].id
    for demo in DEMO_DRIVERS:
        profile = await driver_profile(session_factory, demo.username)
        assert profile.approval_status is ApprovalStatus.APPROVED
        assert profile.approved_by == admin_id
        assert profile.is_online
        assert (profile.full_name, profile.phone, profile.license_number) == (
            demo.full_name,
            demo.phone,
            demo.license_number,
        )
        assert profile.vehicle is not None
        assert profile.vehicle.plate_number == demo.vehicle.plate_number
        assert (profile.longitude, profile.latitude) == demo.location.as_lon_lat()
        assert profile.location_updated_at == clock.now()


async def test_demo_drivers_are_found_near_the_almaty_center_nearest_first(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)

    users = await users_by_name(session_factory)
    expected = [users[demo.username].id for demo in DEMO_DRIVERS]
    assert await nearby_driver_ids(session_factory, clock) == expected


async def test_second_run_creates_nothing_and_changes_nothing(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)
    counts = await row_counts(session_factory)
    hashes = {
        name: user.password_hash for name, user in (await users_by_name(session_factory)).items()
    }
    clock.advance(timedelta(minutes=5))

    report = await run_seed(session_factory, clock, hasher)

    assert (report.count("created"), report.count("skipped")) == (0, 6)
    assert all("already exists" in entry.detail for entry in report.entries)
    assert await row_counts(session_factory) == counts
    after = {
        name: user.password_hash for name, user in (await users_by_name(session_factory)).items()
    }
    assert after == hashes
    profile = await driver_profile(session_factory, "demo_driver_1")
    assert profile.location_updated_at == clock.now() - timedelta(minutes=5)


async def test_nothing_to_create_needs_no_password(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    assert (await plan_demo_seed(session_factory)).missing == DEMO_USERNAMES
    await run_seed(session_factory, clock, hasher)

    plan = await plan_demo_seed(session_factory)
    report = await apply_demo_seed(session_factory, plan, clock=clock, hasher=hasher, password=None)

    assert plan.missing == ()
    assert report.count("skipped") == 6


async def test_rerun_keeps_changes_made_through_the_application(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)
    users = await users_by_name(session_factory)
    async with session_factory() as session:
        await DriverService(session, clock).update_profile(
            users["demo_driver_1"].id, DriverProfileUpdate(phone="+77019998877")
        )
    async with session_factory() as session:
        await UserService(session, clock, hasher).update_profile(
            users["demo_passenger_1"].id, MyProfileUpdate(display_name="Aigerim")
        )
    async with session_factory() as session:
        await DriverService(session, clock).set_availability(
            users["demo_driver_3"].id, online=False
        )

    await run_seed(session_factory, clock, hasher)

    assert (await driver_profile(session_factory, "demo_driver_1")).phone == "+77019998877"
    assert not (await driver_profile(session_factory, "demo_driver_3")).is_online
    async with session_factory() as session:
        profile = await UserService(session, clock, hasher).get_profile(
            users["demo_passenger_1"].id
        )
    assert profile is not None
    assert profile.display_name == "Aigerim"


async def test_refresh_locations_restamps_demo_drivers_with_the_clock(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)
    users = await users_by_name(session_factory)
    moved = Coordinates(longitude=76.90, latitude=43.30)
    async with session_factory() as session:
        await DriverService(session, clock).update_location(users["demo_driver_2"].id, moved)
    async with session_factory() as session:
        await DriverService(session, clock).set_availability(
            users["demo_driver_3"].id, online=False
        )
    clock.advance(timedelta(minutes=5))
    assert await nearby_driver_ids(session_factory, clock) == []

    report = await run_seed(session_factory, clock, hasher, refresh_locations=True)

    assert (report.count("created"), report.count("refreshed")) == (0, 3)
    for demo in DEMO_DRIVERS:
        profile = await driver_profile(session_factory, demo.username)
        assert profile.location_updated_at == clock.now()
        assert (profile.longitude, profile.latitude) == demo.location.as_lon_lat()
        assert profile.is_online
    assert await nearby_driver_ids(session_factory, clock) == [
        users[demo.username].id for demo in DEMO_DRIVERS
    ]


async def test_refresh_locations_never_reapproves_or_rewrites_a_profile(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await run_seed(session_factory, clock, hasher)
    users = await users_by_name(session_factory)
    changed_vehicle = DriverProfileUpdate.model_validate(
        {
            "vehicle": {
                "make": "Lada",
                "model": "Vesta",
                "color": "red",
                "plate_number": "777AAA02",
                "year": 2022,
            }
        }
    )
    async with session_factory() as session:
        await DriverService(session, clock).update_profile(
            users["demo_driver_1"].id, changed_vehicle
        )

    report = await run_seed(session_factory, clock, hasher, refresh_locations=True)

    profile = await driver_profile(session_factory, "demo_driver_1")
    assert profile.approval_status is ApprovalStatus.PENDING
    assert not profile.is_online
    assert profile.vehicle is not None
    assert profile.vehicle.plate_number == "777AAA02"
    assert "not approved" in entry_for(report, "demo_driver_1")


async def test_refresh_locations_touches_only_demo_drivers(
    session_factory: SessionFactory,
    clock: ManualClock,
    hasher: PasswordHasher,
    driver_factory: DriverFactory,
) -> None:
    other = await driver_factory.driver("someone_else", location=DEMO_PICKUP)
    await run_seed(session_factory, clock, hasher)
    stamped = clock.now()
    clock.advance(timedelta(minutes=5))

    await run_seed(session_factory, clock, hasher, refresh_locations=True)

    async with session_factory() as session:
        profile = await DriverService(session, clock).get(other)
    assert profile is not None
    assert profile.location_updated_at == stamped


async def test_demo_username_taken_with_another_role_is_a_conflict(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    async with session_factory() as session:
        await UserService(session, clock, hasher).create_user(
            username="Demo_Driver_2", password=DEMO_PASSWORD, role=UserRole.PASSENGER
        )

    with pytest.raises(DemoSeedConflictError, match="demo_driver_2"):
        await run_seed(session_factory, clock, hasher)

    assert list(await users_by_name(session_factory)) == ["Demo_Driver_2"]


async def test_demo_plate_used_by_another_driver_is_a_conflict(
    session_factory: SessionFactory,
    clock: ManualClock,
    hasher: PasswordHasher,
    driver_factory: DriverFactory,
) -> None:
    other = await driver_factory.driver("someone_else", approved=False)
    async with session_factory() as session:
        await DriverService(session, clock).update_profile(
            other,
            DriverProfileUpdate.model_validate(
                {
                    "vehicle": {
                        "make": "Lada",
                        "model": "Vesta",
                        "color": "red",
                        "plate_number": "demo 001-kz",
                        "year": 2022,
                    }
                }
            ),
        )
    before = await row_counts(session_factory)

    with pytest.raises(DemoSeedConflictError, match="DEMO001KZ"):
        await run_seed(session_factory, clock, hasher)

    assert await row_counts(session_factory) == before


def test_demo_data_is_consistent() -> None:
    plates = [demo.vehicle.plate_number for demo in DEMO_DRIVERS]
    assert len(set(plates)) == len(plates)
    assert len(set(DEMO_USERNAMES)) == len(DEMO_USERNAMES) == 1 + len(DEMO_PASSENGERS) + 3
    assert all(name.startswith("demo_") for name in DEMO_USERNAMES)
