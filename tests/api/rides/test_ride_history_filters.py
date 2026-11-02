"""GET /api/v1/rides filters: ``status`` (repeatable) and ``[created_from, created_to)``."""

import uuid
from datetime import timedelta, timezone

import httpx
import pytest

from support.clock import DEFAULT_START
from support.drivers import DriverFactory, login_as
from support.history import get_page, ids_of, newest_first, past_rides
from support.rides import RIDES_URL, RideFactory
from taxi_service.modules.rides.states import RideStatus

ALMATY = timezone(timedelta(hours=5))


def at(minutes: int) -> str:
    """ISO time ``minutes`` after the test clock's start, in UTC."""
    return (DEFAULT_START + timedelta(minutes=minutes)).isoformat()


@pytest.fixture
async def pat(ride_factory: RideFactory) -> uuid.UUID:
    return await ride_factory.passenger("pat")


@pytest.fixture
async def minutes_1_2_3(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> list[uuid.UUID]:
    """Three rides of pat created at start + 1, 2 and 3 minutes; logged in as pat."""
    rides = await past_rides(ride_factory, pat, 3)
    await login_as(client, "pat")
    return rides


# Status ----------------------------------------------------------------------


async def test_filter_by_one_status(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    cancelled = await past_rides(ride_factory, pat, 2)
    await past_rides(ride_factory, pat, 1, status=RideStatus.NO_DRIVER)
    await login_as(client, "pat")

    body = await get_page(client, RIDES_URL, status="cancelled")

    assert (ids_of(body), body["total"]) == (newest_first(cancelled), 2)


async def test_filter_by_several_statuses(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    wanted = await past_rides(ride_factory, pat, 1, status=RideStatus.NO_DRIVER)
    await past_rides(ride_factory, pat, 1)
    wanted.append((await ride_factory.searching_ride(pat)).id)
    await login_as(client, "pat")

    body = await get_page(client, RIDES_URL, status=["searching", "no_driver"])

    assert (ids_of(body), body["total"]) == (newest_first(wanted), 2)


async def test_status_filter_never_reaches_another_passenger(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    await past_rides(ride_factory, pat, 1)
    bob = await ride_factory.passenger("bob")
    await past_rides(ride_factory, bob, 3, status=RideStatus.NO_DRIVER)
    await login_as(client, "pat")

    body = await get_page(client, RIDES_URL, status="no_driver", limit=100)

    assert (body["items"], body["total"]) == ([], 0)


async def test_driver_filters_their_rides_by_status(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    pat: uuid.UUID,
) -> None:
    dana = await driver_factory.driver("dana")
    completed = await past_rides(ride_factory, pat, 1, status=RideStatus.COMPLETED, driver_id=dana)
    await past_rides(ride_factory, pat, 1, status=RideStatus.CANCELLED, driver_id=dana)
    await login_as(client, "dana")

    body = await get_page(client, RIDES_URL, status="completed")

    assert ids_of(body) == newest_first(completed)


async def test_unknown_status_is_rejected(client: httpx.AsyncClient, pat: uuid.UUID) -> None:
    await login_as(client, "pat")

    response = await client.get(RIDES_URL, params={"status": "lost"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# Dates -----------------------------------------------------------------------


async def test_created_from_is_inclusive(
    client: httpx.AsyncClient, minutes_1_2_3: list[uuid.UUID]
) -> None:
    body = await get_page(client, RIDES_URL, created_from=at(2))

    assert (ids_of(body), body["total"]) == (newest_first(minutes_1_2_3[1:]), 2)


async def test_created_to_is_exclusive(
    client: httpx.AsyncClient, minutes_1_2_3: list[uuid.UUID]
) -> None:
    body = await get_page(client, RIDES_URL, created_to=at(2))

    assert (ids_of(body), body["total"]) == (newest_first(minutes_1_2_3[:1]), 1)


async def test_both_bounds_select_a_window(
    client: httpx.AsyncClient, minutes_1_2_3: list[uuid.UUID]
) -> None:
    body = await get_page(client, RIDES_URL, created_from=at(2), created_to=at(3))

    assert ids_of(body) == [str(minutes_1_2_3[1])]


async def test_bounds_with_an_offset_are_compared_in_utc(
    client: httpx.AsyncClient, minutes_1_2_3: list[uuid.UUID]
) -> None:
    from_almaty = (DEFAULT_START + timedelta(minutes=3)).astimezone(ALMATY).isoformat()

    body = await get_page(client, RIDES_URL, created_from=from_almaty)

    assert from_almaty.endswith("+05:00")
    assert ids_of(body) == [str(minutes_1_2_3[2])]


async def test_equal_bounds_give_an_empty_page(
    client: httpx.AsyncClient, minutes_1_2_3: list[uuid.UUID]
) -> None:
    body = await get_page(client, RIDES_URL, created_from=at(2), created_to=at(2))

    assert (body["items"], body["total"]) == ([], 0)


async def test_bounds_combine_with_status_and_pages(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    rides = await past_rides(ride_factory, pat, 5)
    await past_rides(ride_factory, pat, 1, status=RideStatus.NO_DRIVER)
    await login_as(client, "pat")

    body = await get_page(
        client, RIDES_URL, status="cancelled", created_from=at(2), limit=2, offset=1
    )

    assert (ids_of(body), body["total"]) == (newest_first(rides)[1:3], 4)


async def test_naive_time_is_rejected(client: httpx.AsyncClient, pat: uuid.UUID) -> None:
    await login_as(client, "pat")

    response = await client.get(RIDES_URL, params={"created_from": "2026-11-03T09:00:00"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_reversed_bounds_are_rejected(client: httpx.AsyncClient, pat: uuid.UUID) -> None:
    await login_as(client, "pat")

    response = await client.get(RIDES_URL, params={"created_from": at(5), "created_to": at(1)})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


# OpenAPI ---------------------------------------------------------------------


async def test_history_documents_its_query_parameters(client: httpx.AsyncClient) -> None:
    operation = (await client.get("/openapi.json")).json()["paths"]["/api/v1/rides"]["get"]

    parameters = {item["name"]: item for item in operation["parameters"]}
    assert set(parameters) == {"limit", "offset", "status", "created_from", "created_to"}
    assert all(item["in"] == "query" for item in parameters.values())
    assert {"200", "401", "403", "422"} <= set(operation["responses"])
    assert {"SessionCookie": []} in operation["security"]
    assert "inclusive" in parameters["created_from"]["description"]
    assert "exclusive" in parameters["created_to"]["description"]
