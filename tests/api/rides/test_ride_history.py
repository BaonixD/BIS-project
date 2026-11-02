"""GET /api/v1/rides: a passenger's own rides and a driver's assigned rides, page by page.

Admins are refused (403): they read every ride through GET /api/v1/admin/rides.
"""

import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest

from support.auth import SESSION_COOKIE, register_and_login
from support.drivers import DriverFactory, login_as
from support.history import ids_of, newest_first, past_rides, set_ride
from support.rides import RIDES_URL, RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.states import RideStatus

SUMMARY_FIELDS = {
    "id",
    "status",
    "passenger_id",
    "driver_id",
    "pickup",
    "dropoff",
    "distance_m",
    "duration_s",
    "amount_kzt",
    "currency",
    "created_at",
    "updated_at",
}


async def history(client: httpx.AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get(RIDES_URL, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def pat(ride_factory: RideFactory) -> uuid.UUID:
    return await ride_factory.passenger("pat")


@pytest.fixture
async def bob(ride_factory: RideFactory) -> uuid.UUID:
    return await ride_factory.passenger("bob")


# Ownership -------------------------------------------------------------------


async def test_passenger_sees_only_their_own_rides(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID, bob: uuid.UUID
) -> None:
    pat_rides = await past_rides(ride_factory, pat, 2)
    bob_rides = await past_rides(ride_factory, bob, 2)
    pat_rides += await past_rides(ride_factory, pat, 1)

    await login_as(client, "pat")
    pat_page = await history(client)
    await login_as(client, "bob")
    bob_page = await history(client)

    assert (ids_of(pat_page), pat_page["total"]) == (newest_first(pat_rides), 3)
    assert (ids_of(bob_page), bob_page["total"]) == (newest_first(bob_rides), 2)


async def test_offset_never_reaches_another_passenger(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID, bob: uuid.UUID
) -> None:
    [own] = await past_rides(ride_factory, pat, 1)
    await past_rides(ride_factory, bob, 5)
    await login_as(client, "pat")

    beyond_own = await history(client, offset=1, limit=100)
    everything = await history(client, limit=100)

    assert (beyond_own["items"], beyond_own["total"]) == ([], 1)
    assert ids_of(everything) == [str(own)]


async def test_active_ride_is_in_the_history(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    ride = await ride_factory.searching_ride(pat)
    await login_as(client, "pat")

    body = await history(client)

    assert ids_of(body) == [str(ride.id)]
    assert body["items"][0]["status"] == "searching"


async def test_driver_sees_only_rides_assigned_to_them(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    pat: uuid.UUID,
    bob: uuid.UUID,
) -> None:
    dana = await driver_factory.driver("dana")
    egor = await driver_factory.driver("egor")
    dana_rides = await past_rides(ride_factory, pat, 1, status=RideStatus.COMPLETED, driver_id=dana)
    await past_rides(ride_factory, pat, 1, status=RideStatus.COMPLETED, driver_id=egor)
    dana_rides += await past_rides(
        ride_factory, bob, 1, status=RideStatus.CANCELLED, driver_id=dana
    )
    await ride_factory.searching_ride(pat)

    await login_as(client, "dana")
    body = await history(client)

    assert (ids_of(body), body["total"]) == (newest_first(dana_rides), 2)
    assert {item["driver_id"] for item in body["items"]} == {str(dana)}


async def test_driver_does_not_see_a_ride_given_to_another_driver(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    pat: uuid.UUID,
) -> None:
    dana = await driver_factory.driver("dana")
    egor = await driver_factory.driver("egor")
    [ride] = await past_rides(ride_factory, pat, 1, status=RideStatus.ASSIGNED, driver_id=dana)
    await set_ride(session_factory, ride, RideStatus.ASSIGNED, egor)

    await login_as(client, "dana")
    body = await history(client)

    assert (body["items"], body["total"]) == ([], 0)


async def test_driver_without_rides_gets_an_empty_page(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    await past_rides(ride_factory, pat, 2)
    await register_and_login(client, "dana", role="driver")

    assert await history(client) == {"items": [], "limit": 20, "offset": 0, "total": 0}


async def test_admin_is_sent_to_the_admin_list(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.admin_id()
    await login_as(client, "admin")

    response = await client.get(RIDES_URL)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_history_needs_a_session(client: httpx.AsyncClient) -> None:
    response = await client.get(RIDES_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# Pages -----------------------------------------------------------------------


async def test_default_page_has_twenty_newest_rides(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    rides = await past_rides(ride_factory, pat, 23)
    await login_as(client, "pat")

    first = await history(client)
    second = await history(client, offset=20)

    assert (first["limit"], first["offset"], first["total"]) == (20, 0, 23)
    assert ids_of(first) == newest_first(rides)[:20]
    assert (second["offset"], ids_of(second)) == (20, newest_first(rides)[20:])


async def test_limit_up_to_one_hundred(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    rides = await past_rides(ride_factory, pat, 3, step=timedelta(0))
    await login_as(client, "pat")

    body = await history(client, limit=100)

    assert (body["limit"], len(body["items"]), body["total"]) == (100, len(rides), 3)


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}])
async def test_page_bounds_are_validated(
    client: httpx.AsyncClient, pat: uuid.UUID, params: dict[str, int]
) -> None:
    await login_as(client, "pat")

    response = await client.get(RIDES_URL, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_offset_past_the_end_gives_an_empty_page_with_the_total(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    await past_rides(ride_factory, pat, 3)
    await login_as(client, "pat")

    body = await history(client, offset=50, limit=10)

    assert body == {"items": [], "limit": 10, "offset": 50, "total": 3}


async def test_rides_created_at_the_same_time_are_ordered_by_id(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    earlier = await past_rides(ride_factory, pat, 1)
    ride_factory.clock.advance(timedelta(minutes=1))
    same_time = await past_rides(ride_factory, pat, 4, step=timedelta(0))
    await login_as(client, "pat")

    pages = [ids_of(await history(client, limit=2, offset=offset)) for offset in (0, 2, 4)]

    expected = sorted((str(ride_id) for ride_id in same_time), key=_id_order, reverse=True)
    assert [ride_id for page in pages for ride_id in page] == [*expected, str(earlier[0])]


async def test_repeating_a_page_gives_the_same_result(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    await past_rides(ride_factory, pat, 6, step=timedelta(0))
    await login_as(client, "pat")

    first = await history(client, limit=3, offset=2)
    again = await history(client, limit=3, offset=2)

    assert first == again


# Response --------------------------------------------------------------------


async def test_items_are_ride_summaries(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    ride = await ride_factory.searching_ride(pat)
    await login_as(client, "pat")

    [item] = (await history(client))["items"]

    assert set(item) == SUMMARY_FIELDS
    assert item["passenger_id"] == str(pat)
    assert item["pickup"] == {"longitude": ride.pickup_longitude, "latitude": ride.pickup_latitude}
    assert (item["amount_kzt"], item["currency"]) == (ride.amount_kzt, "KZT")
    assert (item["distance_m"], item["duration_s"]) == (ride.distance_m, ride.duration_s)
    assert item["created_at"].endswith("Z")


async def test_history_reveals_no_route_geometry_or_secrets(
    client: httpx.AsyncClient, ride_factory: RideFactory, pat: uuid.UUID
) -> None:
    await ride_factory.searching_ride(pat)
    user = await login_as(client, "pat")

    text = (await client.get(RIDES_URL)).text

    session_token = client.cookies.get(SESSION_COOKIE)
    assert session_token
    for secret in ("route_geometry", "coordinates", "password", "$argon2", "csrf", "token"):
        assert secret not in text
    assert user.csrf_token not in text
    assert session_token not in text


def _id_order(ride_id: str) -> str:
    return uuid.UUID(ride_id).hex
