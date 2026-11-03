"""PUT /drivers/me/availability: online only for an approved, complete driver."""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.clock import ManualClock
from support.drivers import (
    AVAILABILITY_URL,
    DRIVERS_ME_URL,
    approve,
    complete_profile,
    create_admin,
    login_as,
    registered_driver,
)
from taxi_service.database.session import SessionFactory


@pytest.mark.parametrize("profile", [None, {"full_name": "Dana"}, complete_profile()])
async def test_driver_cannot_go_online_before_approval(
    client: httpx.AsyncClient, profile: dict[str, Any] | None
) -> None:
    driver = await registered_driver(client, "dana", profile=profile)

    response = await client.put(
        AVAILABILITY_URL, json={"online": True}, headers=driver.csrf_headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "driver_not_approved"
    assert (await client.get(DRIVERS_ME_URL)).json()["online"] is False


async def test_going_offline_is_always_allowed(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.put(
        AVAILABILITY_URL, json={"online": False}, headers=driver.csrf_headers
    )

    assert response.status_code == 200
    assert response.json()["online"] is False


async def test_approved_driver_goes_online_and_offline(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    await create_admin(app, session_factory, clock)
    driver = await registered_driver(client, "dana", profile=complete_profile())
    assert (await approve(client, driver.id)).status_code == 200
    driver = await login_as(client, "dana")

    online = await client.put(AVAILABILITY_URL, json={"online": True}, headers=driver.csrf_headers)
    again = await client.put(AVAILABILITY_URL, json={"online": True}, headers=driver.csrf_headers)
    offline = await client.put(
        AVAILABILITY_URL, json={"online": False}, headers=driver.csrf_headers
    )

    assert (online.status_code, online.json()["online"]) == (200, True)
    assert (again.status_code, again.json()["online"]) == (200, True)
    assert (offline.status_code, offline.json()["online"]) == (200, False)


@pytest.mark.parametrize(
    "body", [{}, {"online": "yes"}, {"online": 1}, {"online": None}, {"online": True, "x": 1}]
)
async def test_malformed_availability_is_rejected(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.put(AVAILABILITY_URL, json=body, headers=driver.csrf_headers)

    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Token": "not-the-session-token"}])
async def test_availability_change_needs_the_csrf_token(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    headers: dict[str, str],
) -> None:
    await create_admin(app, session_factory, clock)
    driver = await registered_driver(client, "dana", profile=complete_profile())
    assert (await approve(client, driver.id)).status_code == 200
    await login_as(client, "dana")

    response = await client.put(AVAILABILITY_URL, json={"online": True}, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert (await client.get(DRIVERS_ME_URL)).json()["online"] is False
