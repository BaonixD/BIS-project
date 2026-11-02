"""PUT /drivers/me/location: one current WGS 84 point, stamped with server time."""

from datetime import timedelta
from typing import Any

import httpx
import pytest

from support.clock import ManualClock
from support.drivers import ALMATY_CENTER, DRIVERS_ME_URL, LOCATION_URL, registered_driver


@pytest.mark.parametrize(
    "point",
    [
        {"longitude": 180, "latitude": 90},
        {"longitude": -180, "latitude": -90},
        {"longitude": 180.0, "latitude": -90.0},
        {"longitude": 0, "latitude": 0},
        ALMATY_CENTER,
    ],
)
async def test_points_within_inclusive_bounds_are_stored(
    client: httpx.AsyncClient, point: dict[str, float]
) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.put(LOCATION_URL, json=point, headers=driver.csrf_headers)

    assert response.status_code == 200
    assert response.json()["location"] == {
        "longitude": float(point["longitude"]),
        "latitude": float(point["latitude"]),
    }
    assert (await client.get(DRIVERS_ME_URL)).json()["location"] == response.json()["location"]


@pytest.mark.parametrize(
    "point",
    [
        {"longitude": 180.000001, "latitude": 43.2},
        {"longitude": -180.000001, "latitude": 43.2},
        {"longitude": 76.9, "latitude": 90.000001},
        {"longitude": 76.9, "latitude": -90.000001},
        # Swapped order: a longitude of 120 sent as the latitude.
        {"longitude": 43.2, "latitude": 120.5},
        [76.9457, 43.2383],
        {"lon": 76.9457, "lat": 43.2383},
        {"longitude": "76.9", "latitude": 43.2},
        {"longitude": 76.9},
        {"longitude": None, "latitude": None},
        {**ALMATY_CENTER, "location_updated_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_out_of_range_swapped_or_malformed_points_are_rejected(
    client: httpx.AsyncClient, point: Any
) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.put(LOCATION_URL, json=point, headers=driver.csrf_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (await client.get(DRIVERS_ME_URL)).json()["location"] is None


async def test_each_update_replaces_the_point_and_takes_server_time(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    driver = await registered_driver(client, "dana")

    first = await client.put(LOCATION_URL, json=ALMATY_CENTER, headers=driver.csrf_headers)
    clock.advance(timedelta(seconds=5, milliseconds=250))
    moved = {"longitude": 76.9286, "latitude": 43.2187}
    second = await client.put(LOCATION_URL, json=moved, headers=driver.csrf_headers)

    assert first.json()["location_updated_at"] == "2026-11-03T09:00:00Z"
    assert second.json()["location_updated_at"] == "2026-11-03T09:00:05.250000Z"
    assert second.json()["location"] == moved
    assert (await client.get(DRIVERS_ME_URL)).json()["location"] == moved


async def test_location_update_needs_the_csrf_token(client: httpx.AsyncClient) -> None:
    await registered_driver(client, "dana")

    response = await client.put(LOCATION_URL, json=ALMATY_CENTER)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
