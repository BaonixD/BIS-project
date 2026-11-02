"""Drivers through the real API: complete profile, admin approval, online, location.

Usage in an API test with the ``app``, ``client``, ``session_factory`` and ``clock`` fixtures::

    admin_id = await create_admin(app, session_factory, clock)
    driver = await approved_driver(client, "driver_1", location=ALMATY_CENTER)
    # the client is now logged in as driver_1

The client keeps one session cookie, so each helper logs in as the user it acts for.
"""

import uuid
from typing import Any

import httpx
from fastapi import FastAPI

from support.auth import PASSWORD, LoggedInUser, current_session, login, register_and_login
from support.clock import ManualClock
from taxi_service.database.session import SessionFactory
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.service import UserService

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
        service = UserService(session, clock, app.state.password_hasher)
        user = await service.create_user(username=username, password=PASSWORD, role=UserRole.ADMIN)
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
