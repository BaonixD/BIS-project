"""Demonstration data: an admin, two passengers and three approved, online drivers.

Run it with ``uv run python scripts/seed.py``; nothing in the application
imports this module. Usernames are the stable keys: an account that already
exists is reported and left as it is, so repeated runs create nothing new and
keep changes made through the API. Only ``refresh_locations`` touches existing
demo drivers, and then only their location and availability.
"""

import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Literal

from sqlalchemy import select

from taxi_service.core.clock import Clock
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.drivers.exceptions import (
    DriverNotApprovedError,
    DriverProfileIncompleteError,
)
from taxi_service.modules.drivers.geodesy import haversine_m
from taxi_service.modules.drivers.models import Vehicle
from taxi_service.modules.drivers.schemas import DriverProfileUpdate
from taxi_service.modules.drivers.service import DriverAdminService, DriverService
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.repository import UserRepository
from taxi_service.modules.users.schemas import MyProfileUpdate
from taxi_service.modules.users.service import UserService

DEMO_ADMIN = "demo_admin"
DEMO_PICKUP = Coordinates(longitude=76.9457, latitude=43.2383)
"""Synthetic reference point in central Almaty; the demo drivers stand 0.3-2.5 km from it."""


@dataclass(frozen=True, slots=True)
class DemoPassenger:
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class DemoVehicle:
    make: str
    model: str
    color: str
    plate_number: str
    year: int


@dataclass(frozen=True, slots=True)
class DemoDriver:
    username: str
    full_name: str
    phone: str
    license_number: str
    vehicle: DemoVehicle
    location: Coordinates


DEMO_PASSENGERS = (
    DemoPassenger("demo_passenger_1", "Demo Passenger 1"),
    DemoPassenger("demo_passenger_2", "Demo Passenger 2"),
)
DEMO_DRIVERS = (
    DemoDriver(
        "demo_driver_1",
        "Demo Driver One",
        "+77000000101",
        "DEMOLIC001",
        DemoVehicle("Toyota", "Camry", "white", "DEMO001KZ", 2020),
        Coordinates(longitude=76.9457, latitude=43.2410),  # ~300 m north
    ),
    DemoDriver(
        "demo_driver_2",
        "Demo Driver Two",
        "+77000000102",
        "DEMOLIC002",
        DemoVehicle("Hyundai", "Elantra", "silver", "DEMO002KZ", 2021),
        Coordinates(longitude=76.9605, latitude=43.2383),  # ~1.2 km east
    ),
    DemoDriver(
        "demo_driver_3",
        "Demo Driver Three",
        "+77000000103",
        "DEMOLIC003",
        DemoVehicle("Kia", "K5", "black", "DEMO003KZ", 2019),
        Coordinates(longitude=76.9240, latitude=43.2225),  # ~2.5 km south-west
    ),
)
DEMO_ROLES: Mapping[str, UserRole] = {
    DEMO_ADMIN: UserRole.ADMIN,
    **{passenger.username: UserRole.PASSENGER for passenger in DEMO_PASSENGERS},
    **{driver.username: UserRole.DRIVER for driver in DEMO_DRIVERS},
}
DEMO_USERNAMES = tuple(DEMO_ROLES)

Action = Literal["created", "skipped", "refreshed"]


class DemoSeedConflictError(Exception):
    """Existing data blocks the seed (wrong role, plate in use); nothing was changed."""


@dataclass(frozen=True, slots=True)
class ExistingAccount:
    id: uuid.UUID
    role: UserRole


@dataclass(frozen=True, slots=True)
class DemoPlan:
    """Demo accounts that already exist, by username; the rest will be created."""

    existing: Mapping[str, ExistingAccount]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(name for name in DEMO_USERNAMES if name not in self.existing)


@dataclass(frozen=True, slots=True)
class SeedEntry:
    action: Action
    role: UserRole
    username: str
    detail: str = ""


@dataclass(slots=True)
class SeedReport:
    entries: list[SeedEntry] = field(default_factory=list)

    def count(self, action: Action) -> int:
        return sum(entry.action == action for entry in self.entries)


async def plan_demo_seed(session_factory: SessionFactory) -> DemoPlan:
    """Read which demo accounts exist; ``DemoSeedConflictError`` if existing data blocks them."""
    async with session_factory() as session, read_transaction(session):
        users = UserRepository(session)
        existing = {}
        for username in DEMO_USERNAMES:
            user = await users.get_by_username(username)
            if user is not None:
                existing[username] = ExistingAccount(id=user.id, role=user.role)
        plan = DemoPlan(existing=existing)
        plates = [demo.vehicle.plate_number for demo in _missing_drivers(plan)]
        taken = set(
            await session.scalars(
                select(Vehicle.plate_number).where(Vehicle.plate_number.in_(plates))
            )
        )
    _check_conflicts(plan, taken)
    return plan


async def apply_demo_seed(
    session_factory: SessionFactory,
    plan: DemoPlan,
    *,
    clock: Clock,
    hasher: PasswordHasher,
    password: str | None,
    refresh_locations: bool = False,
) -> SeedReport:
    """Create the accounts the plan lists as missing; skip (or refresh) the others.

    ``password`` is needed only when something is missing; every created
    account gets it. Each step runs through the services in its own transaction.
    """
    if plan.missing and password is None:
        raise ValueError("a password is required to create the missing demo accounts")
    seeder = _DemoSeeder(session_factory, clock, hasher, password, plan, refresh_locations)
    admin_id, admin_entry = await seeder.admin()
    report = SeedReport([admin_entry])
    for passenger in DEMO_PASSENGERS:
        report.entries.append(await seeder.passenger(passenger))
    for driver in DEMO_DRIVERS:
        report.entries.append(await seeder.driver(driver, admin_id))
    return report


async def seed_demo(
    session_factory: SessionFactory,
    *,
    clock: Clock,
    hasher: PasswordHasher,
    password: str,
    refresh_locations: bool = False,
) -> SeedReport:
    """:func:`plan_demo_seed` followed by :func:`apply_demo_seed`."""
    plan = await plan_demo_seed(session_factory)
    return await apply_demo_seed(
        session_factory,
        plan,
        clock=clock,
        hasher=hasher,
        password=password,
        refresh_locations=refresh_locations,
    )


@dataclass(frozen=True, slots=True)
class _DemoSeeder:
    session_factory: SessionFactory
    clock: Clock
    hasher: PasswordHasher
    password: str | None
    plan: DemoPlan
    refresh_locations: bool

    async def admin(self) -> tuple[uuid.UUID, SeedEntry]:
        existing = self.plan.existing.get(DEMO_ADMIN)
        if existing is not None:
            return existing.id, _skipped(UserRole.ADMIN, DEMO_ADMIN)
        admin_id = await self._create_user(DEMO_ADMIN, UserRole.ADMIN)
        return admin_id, SeedEntry("created", UserRole.ADMIN, DEMO_ADMIN)

    async def passenger(self, passenger: DemoPassenger) -> SeedEntry:
        if passenger.username in self.plan.existing:
            return _skipped(UserRole.PASSENGER, passenger.username)
        user_id = await self._create_user(passenger.username, UserRole.PASSENGER)
        async with self.session_factory() as session:
            await UserService(session, self.clock, self.hasher).update_profile(
                user_id, MyProfileUpdate(display_name=passenger.display_name)
            )
        return SeedEntry("created", UserRole.PASSENGER, passenger.username)

    async def driver(self, driver: DemoDriver, admin_id: uuid.UUID) -> SeedEntry:
        existing = self.plan.existing.get(driver.username)
        if existing is None:
            await self._create_driver(driver, admin_id)
            return SeedEntry("created", UserRole.DRIVER, driver.username, _whereabouts(driver))
        if not self.refresh_locations:
            return _skipped(UserRole.DRIVER, driver.username)
        try:
            await self._place_online(existing.id, driver.location)
        except (DriverNotApprovedError, DriverProfileIncompleteError):
            detail = "location refreshed; left offline: not approved (profile changed)"
            return SeedEntry("refreshed", UserRole.DRIVER, driver.username, detail)
        return SeedEntry("refreshed", UserRole.DRIVER, driver.username, _whereabouts(driver))

    async def _create_user(self, username: str, role: UserRole) -> uuid.UUID:
        if self.password is None:
            raise ValueError("a password is required to create demo accounts")
        async with self.session_factory() as session:
            service = UserService(session, self.clock, self.hasher)
            user = await service.create_user(username=username, password=self.password, role=role)
        return user.id

    async def _create_driver(self, driver: DemoDriver, admin_id: uuid.UUID) -> None:
        user_id = await self._create_user(driver.username, UserRole.DRIVER)
        async with self.session_factory() as session:
            await DriverService(session, self.clock).update_profile(user_id, _profile(driver))
        async with self.session_factory() as session:
            await DriverAdminService(session, self.clock).approve(user_id, admin_id=admin_id)
        await self._place_online(user_id, driver.location)

    async def _place_online(self, driver_id: uuid.UUID, location: Coordinates) -> None:
        """Location stamped with the clock now, then online (approved drivers only)."""
        async with self.session_factory() as session:
            await DriverService(session, self.clock).update_location(driver_id, location)
        async with self.session_factory() as session:
            await DriverService(session, self.clock).set_availability(driver_id, online=True)


def _check_conflicts(plan: DemoPlan, taken_plates: set[str]) -> None:
    for username, account in plan.existing.items():
        expected = DEMO_ROLES[username]
        if account.role is not expected:
            raise DemoSeedConflictError(
                f"{username} already exists as {account.role.value}, not {expected.value}"
            )
    for driver in _missing_drivers(plan):
        if driver.vehicle.plate_number in taken_plates:
            raise DemoSeedConflictError(
                f"plate {driver.vehicle.plate_number} of {driver.username}"
                " is registered to another driver"
            )


def _missing_drivers(plan: DemoPlan) -> list[DemoDriver]:
    return [driver for driver in DEMO_DRIVERS if driver.username not in plan.existing]


def _profile(driver: DemoDriver) -> DriverProfileUpdate:
    return DriverProfileUpdate.model_validate(
        {
            "full_name": driver.full_name,
            "phone": driver.phone,
            "license_number": driver.license_number,
            "vehicle": asdict(driver.vehicle),
        }
    )


def _skipped(role: UserRole, username: str) -> SeedEntry:
    return SeedEntry("skipped", role, username, "already exists; not changed")


def _whereabouts(driver: DemoDriver) -> str:
    distance = haversine_m(DEMO_PICKUP, driver.location)
    return f"{driver.vehicle.plate_number}, online ~{distance:.0f} m from the demo pickup"
