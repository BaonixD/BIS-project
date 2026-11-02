"""Demonstration data: an admin, two passengers and three approved, online drivers.

Run it with ``uv run python scripts/seed.py``; nothing in the application
imports this module. Usernames are the stable keys: an account that already
exists is reported and left as it is, so repeated runs create nothing new and
keep changes made through the API. Only ``refresh_locations`` touches existing
demo drivers, and then only their location and availability.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from taxi_service.core.clock import Clock
from taxi_service.database.session import SessionFactory
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.users.models import UserRole

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
DEMO_USERNAMES = (
    DEMO_ADMIN,
    *(passenger.username for passenger in DEMO_PASSENGERS),
    *(driver.username for driver in DEMO_DRIVERS),
)

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
    raise NotImplementedError


async def apply_demo_seed(
    session_factory: SessionFactory,
    plan: DemoPlan,
    *,
    clock: Clock,
    hasher: PasswordHasher,
    password: str | None,
    refresh_locations: bool = False,
) -> SeedReport:
    raise NotImplementedError


async def seed_demo(
    session_factory: SessionFactory,
    *,
    clock: Clock,
    hasher: PasswordHasher,
    password: str,
    refresh_locations: bool = False,
) -> SeedReport:
    raise NotImplementedError
