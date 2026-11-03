"""A driver on an active ride cannot go offline or change the profile or car (ADR 0007).

The passenger sees the driver's name, phone and car until the trip ends, and an
online driver keeps the ride; 409 ``driver_on_active_ride`` until the ride is
completed, cancelled or released. Location updates go on as usual.
"""

from typing import Any

import httpx
import pytest

from support.dispatch import Dispatcher
from support.drivers import AVAILABILITY_URL, DRIVERS_ME_URL, LOCATION_URL, DriverFactory, login_as
from support.lifecycle import Trip, expect_ok, trip_in

ACTIVE = ("assigned", "arrived", "in_progress")
CHANGES = [
    {"phone": "+77017654321"},
    {"full_name": "Dana Other"},
    {
        "vehicle": {
            "make": "Kia",
            "model": "Rio",
            "color": "red",
            "plate_number": "777KIA02",
            "year": 2021,
        }
    },
]
ACTIVE_RIDE_ERROR = {
    "code": "driver_on_active_ride",
    "message": "The driver has an active ride; complete or release it first.",
    "details": {},
}


async def my_profile(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get(DRIVERS_ME_URL)
    assert response.status_code == 200, response.text
    profile: dict[str, Any] = response.json()
    return profile


async def as_driver(client: httpx.AsyncClient, trip: Trip) -> dict[str, str]:
    return (await login_as(client, trip.driver)).csrf_headers


@pytest.mark.parametrize("status", ACTIVE)
async def test_driver_cannot_go_offline_during_a_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    headers = await as_driver(client, trip)

    response = await client.put(AVAILABILITY_URL, json={"online": False}, headers=headers)

    assert response.status_code == 409, response.text
    assert response.json()["error"] == ACTIVE_RIDE_ERROR
    assert (await my_profile(client))["online"] is True


@pytest.mark.parametrize("status", ACTIVE)
@pytest.mark.parametrize("change", CHANGES)
async def test_driver_cannot_change_profile_or_car_during_a_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    status: str,
    change: dict[str, Any],
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    headers = await as_driver(client, trip)
    before = await my_profile(client)

    response = await client.patch(DRIVERS_ME_URL, json=change, headers=headers)

    assert response.status_code == 409, response.text
    assert response.json()["error"] == ACTIVE_RIDE_ERROR
    assert await my_profile(client) == before


@pytest.mark.parametrize("status", ACTIVE)
async def test_driver_keeps_sending_locations_and_staying_online(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    headers = await as_driver(client, trip)

    moved = await client.put(
        LOCATION_URL, json={"longitude": 76.9575, "latitude": 43.2391}, headers=headers
    )
    online = await client.put(AVAILABILITY_URL, json={"online": True}, headers=headers)

    assert moved.status_code == 200, moved.text
    assert online.status_code == 200, online.text


@pytest.mark.parametrize("finish", ["complete", "cancel", "release"])
async def test_driver_is_free_again_after_the_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, finish: str
) -> None:
    trip = await trip_in(
        "in_progress" if finish == "complete" else "assigned", client, driver_factory, dispatcher
    )
    await expect_ok(client, trip, finish)
    headers = await as_driver(client, trip)

    changed = await client.patch(DRIVERS_ME_URL, json={"phone": "+77017654321"}, headers=headers)
    offline = await client.put(AVAILABILITY_URL, json={"online": False}, headers=headers)

    assert changed.status_code == 200, changed.text
    assert offline.status_code == 200, offline.text
    assert offline.json()["online"] is False
