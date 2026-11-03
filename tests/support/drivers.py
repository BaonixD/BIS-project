"""Drivers through the real API: complete profile, admin approval, online, location.

Usage in an API test with the ``app``, ``client``, ``session_factory`` and ``clock`` fixtures::

    admin_id = await create_admin(app, session_factory, clock)
    driver = await approved_driver(client, "driver_1", location=ALMATY_CENTER)
    # the client is now logged in as driver_1

The client keeps one session cookie, so each helper logs in as the user it acts for.
For many drivers without HTTP (search, dispatch) use ``DriverFactory`` (fixture
``driver_factory``).
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI

from support.auth import PASSWORD, LoggedInUser, current_session, login, register_and_login
from support.clock import ManualClock
from taxi_service.database.session import SessionFactory
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.drivers import service as driver_service
from taxi_service.modules.drivers.schemas import DriverProfileUpdate
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import UserRole

DRIVERS_ME_URL = "/api/v1/drivers/me"
AVAILABILITY_URL = f"{DRIVERS_ME_URL}/availability"
LOCATION_URL = f"{DRIVERS_ME_URL}/location"
ADMIN_DRIVERS_URL = "/api/v1/admin/drivers"
ADMIN_USERNAME = "admin"

ALMATY_CENTER = {"longitude": 76.9457, "latitude": 43.2383}


def approve_url(driver_id: uuid.UUID | str) -> str:
    return f"{ADMIN_DRIVERS_URL}/{driver_id}/approve"


def vehicle(plate_number: str = "123ABC02", **changes: Any) -> dict[str, Any]:
    return {
        "make": "Toyota",
        "model": "Camry",
        "color": "white",
        "plate_number": plate_number,
        "year": 2020,
        **changes,
    }


def complete_profile(plate_number: str = "123ABC02") -> dict[str, Any]:
    """PATCH body that makes a driver eligible for approval."""
    return {
        "full_name": "Dana Driver",
        "phone": "+77011234567",
        "license_number": "KZ1234567",
        "vehicle": vehicle(plate_number),
    }


async def create_admin(
    app: FastAPI,
    session_factory: SessionFactory,
    clock: ManualClock,
    username: str = ADMIN_USERNAME,
) -> uuid.UUID:
    """Admin account as ``scripts/create_admin.py`` makes it (not via the public API)."""
    async with session_factory() as session:
        user = await users_service.create_user(
            session,
            username,
            PASSWORD,
            UserRole.ADMIN,
            clock=clock,
            hasher=app.state.password_hasher,
        )
    return user.id


async def login_as(client: httpx.AsyncClient, username: str) -> LoggedInUser:
    response = await login(client, username)
    assert response.status_code == 200, response.text
    return await current_session(client)


async def registered_driver(
    client: httpx.AsyncClient, username: str, *, profile: dict[str, Any] | None = None
) -> LoggedInUser:
    """Register and log in a driver; with ``profile`` also PATCH it."""
    driver = await register_and_login(client, username, role="driver")
    if profile is not None:
        response = await client.patch(DRIVERS_ME_URL, json=profile, headers=driver.csrf_headers)
        assert response.status_code == 200, response.text
    return driver


async def approve(
    client: httpx.AsyncClient, driver_id: uuid.UUID, *, admin_username: str = ADMIN_USERNAME
) -> httpx.Response:
    """Log in as the admin and approve; the client stays logged in as the admin."""
    admin = await login_as(client, admin_username)
    return await client.post(approve_url(driver_id), headers=admin.csrf_headers)


async def approved_driver(
    client: httpx.AsyncClient,
    username: str,
    *,
    plate_number: str = "123ABC02",
    location: dict[str, float] | None = None,
    online: bool = True,
    admin_username: str = ADMIN_USERNAME,
) -> LoggedInUser:
    """Complete, approved driver (optionally online with a location); the client ends
    logged in as this driver. The admin account must already exist."""
    driver = await registered_driver(client, username, profile=complete_profile(plate_number))
    approved = await approve(client, driver.id, admin_username=admin_username)
    assert approved.status_code == 200, approved.text
    driver = await login_as(client, username)
    if location is not None:
        response = await client.put(LOCATION_URL, json=location, headers=driver.csrf_headers)
        assert response.status_code == 200, response.text
    if online:
        response = await client.put(
            AVAILABILITY_URL, json={"online": True}, headers=driver.csrf_headers
        )
        assert response.status_code == 200, response.text
    return driver


@dataclass
class DriverFactory:
    """Drivers created through the services, without HTTP: for search and dispatch tests.

    Fixture ``driver_factory``. Accounts get the shared test ``PASSWORD``, so
    they can still log in through the API. Locations are stamped with the
    test clock at the time of the call; move ``clock`` to make them stale.
    """

    session_factory: SessionFactory
    clock: ManualClock
    hasher: PasswordHasher
    _admin_id: uuid.UUID | None = None
    _plates: int = 0

    async def admin_id(self) -> uuid.UUID:
        if self._admin_id is None:
            self._admin_id = await self._create_user(ADMIN_USERNAME, UserRole.ADMIN)
        return self._admin_id

    async def driver(
        self,
        username: str,
        *,
        location: Coordinates | None = None,
        approved: bool = True,
        online: bool = True,
        car_class: Tariff | None = None,
    ) -> uuid.UUID:
        """A complete driver with a unique plate; approved and online unless told otherwise.

        ``car_class`` is set by the approving admin (economy when omitted).
        """
        driver_id = await self._create_user(username, UserRole.DRIVER)
        self._plates += 1
        profile = DriverProfileUpdate.model_validate(complete_profile(f"{self._plates:03d}TST02"))
        async with self.session_factory() as session:
            await driver_service.update_profile(session, driver_id, profile, clock=self.clock)
        if approved:
            admin_id = await self.admin_id()
            async with self.session_factory() as session:
                await driver_service.approve_driver(
                    session, driver_id, admin_id, car_class=car_class, clock=self.clock
                )
        if location is not None:
            await self.move(driver_id, location)
        if approved and online:
            async with self.session_factory() as session:
                await driver_service.set_availability(session, driver_id, True, clock=self.clock)
        return driver_id

    async def go_offline(self, driver_id: uuid.UUID) -> None:
        async with self.session_factory() as session:
            await driver_service.set_availability(session, driver_id, False, clock=self.clock)

    async def move(self, driver_id: uuid.UUID, location: Coordinates) -> None:
        """New location stamped with the current test clock."""
        async with self.session_factory() as session:
            await driver_service.update_location(session, driver_id, location, clock=self.clock)

    async def _create_user(self, username: str, role: UserRole) -> uuid.UUID:
        async with self.session_factory() as session:
            user = await users_service.create_user(
                session, username, PASSWORD, role, clock=self.clock, hasher=self.hasher
            )
        return user.id
