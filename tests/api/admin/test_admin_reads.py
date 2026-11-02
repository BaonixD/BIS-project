"""GET /admin/rides and GET /admin/users: read-only lists for admins."""

import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest

from support.auth import SESSION_COOKIE, register_and_login
from support.clock import DEFAULT_START, ManualClock
from support.drivers import DriverFactory, login_as
from support.history import (
    ADMIN_RIDES_URL,
    ADMIN_USERS_URL,
    ids_of,
    newest_first,
    past_rides,
)
from support.rides import RideFactory
from taxi_service.modules.rides.states import RideStatus

ADMIN_URLS = [ADMIN_RIDES_URL, ADMIN_USERS_URL]
RIDE_FIELDS = {
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
USER_FIELDS = {"id", "username", "role", "created_at", "display_name"}


async def listing(client: httpx.AsyncClient, url: str, **params: Any) -> dict[str, Any]:
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def admin_id(driver_factory: DriverFactory) -> uuid.UUID:
    return await driver_factory.admin_id()


async def as_admin(client: httpx.AsyncClient) -> None:
    await login_as(client, "admin")


# Access ----------------------------------------------------------------------


@pytest.mark.parametrize("url", ADMIN_URLS)
@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_other_roles_are_forbidden(client: httpx.AsyncClient, url: str, role: str) -> None:
    await register_and_login(client, "mallory", role=role)

    response = await client.get(url)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("url", ADMIN_URLS)
async def test_admin_lists_need_a_session(client: httpx.AsyncClient, url: str) -> None:
    response = await client.get(url)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_there_is_no_way_to_change_users_or_rides(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID, method: str
) -> None:
    ride = await ride_factory.searching_ride()
    admin = await login_as(client, "admin")
    body = {"role": "admin", "status": "completed"}

    statuses = [
        (await client.request(method, url, json=body, headers=admin.csrf_headers)).status_code
        for url in (
            ADMIN_USERS_URL,
            f"{ADMIN_USERS_URL}/{ride.passenger_id}",
            ADMIN_RIDES_URL,
            f"{ADMIN_RIDES_URL}/{ride.id}",
        )
    ]
    users = await listing(client, ADMIN_USERS_URL, role="passenger")
    rides = await listing(client, ADMIN_RIDES_URL)

    assert set(statuses) <= {404, 405}
    assert [item["role"] for item in users["items"]] == ["passenger"]
    assert [item["status"] for item in rides["items"]] == ["searching"]


# Rides -----------------------------------------------------------------------


async def test_admin_sees_every_ride_newest_first(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    pat = await ride_factory.passenger("pat")
    bob = await ride_factory.passenger("bob")
    rides = await past_rides(ride_factory, pat, 2)
    rides += await past_rides(ride_factory, bob, 1)
    rides.append((await ride_factory.searching_ride(pat)).id)
    await as_admin(client)

    body = await listing(client, ADMIN_RIDES_URL)

    assert (ids_of(body), body["total"]) == (newest_first(rides), 4)
    assert set(body["items"][0]) == RIDE_FIELDS


async def test_admin_filters_rides_by_passenger_and_driver(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    admin_id: uuid.UUID,
) -> None:
    pat = await ride_factory.passenger("pat")
    bob = await ride_factory.passenger("bob")
    dana = await driver_factory.driver("dana")
    pat_rides = await past_rides(ride_factory, pat, 2)
    dana_rides = await past_rides(ride_factory, bob, 1, status=RideStatus.COMPLETED, driver_id=dana)
    dana_rides += await past_rides(
        ride_factory, pat, 1, status=RideStatus.COMPLETED, driver_id=dana
    )
    await as_admin(client)

    by_bob = await listing(client, ADMIN_RIDES_URL, passenger_id=str(bob))
    by_dana = await listing(client, ADMIN_RIDES_URL, driver_id=str(dana))
    pat_with_dana = await listing(
        client, ADMIN_RIDES_URL, passenger_id=str(pat), driver_id=str(dana)
    )
    pat_cancelled = await listing(
        client, ADMIN_RIDES_URL, passenger_id=str(pat), status="cancelled"
    )

    assert ids_of(by_bob) == [str(dana_rides[0])]
    assert (ids_of(by_dana), by_dana["total"]) == (newest_first(dana_rides), 2)
    assert ids_of(pat_with_dana) == [str(dana_rides[1])]
    assert ids_of(pat_cancelled) == newest_first(pat_rides)


async def test_admin_filters_rides_by_creation_time(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    rides = await past_rides(ride_factory, await ride_factory.passenger(), 4)
    await as_admin(client)

    body = await listing(
        client,
        ADMIN_RIDES_URL,
        created_from=(DEFAULT_START + timedelta(minutes=2)).isoformat(),
        created_to=(DEFAULT_START + timedelta(minutes=4)).isoformat(),
    )

    assert ids_of(body) == newest_first(rides[1:3])


async def test_unknown_participant_gives_an_empty_page(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    await ride_factory.searching_ride()
    await as_admin(client)

    body = await listing(client, ADMIN_RIDES_URL, passenger_id=str(uuid.uuid4()))

    assert (body["items"], body["total"]) == ([], 0)


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 101},
        {"offset": -1},
        {"passenger_id": "not-a-uuid"},
        {"driver_id": "42"},
        {"status": "lost"},
        {"created_to": "2026-11-03T09:00:00"},
    ],
)
async def test_admin_ride_parameters_are_validated(
    client: httpx.AsyncClient, admin_id: uuid.UUID, params: dict[str, Any]
) -> None:
    await as_admin(client)

    response = await client.get(ADMIN_RIDES_URL, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_admin_ride_pages(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    rides = await past_rides(ride_factory, await ride_factory.passenger(), 22)
    await as_admin(client)

    first = await listing(client, ADMIN_RIDES_URL)
    past_end = await listing(client, ADMIN_RIDES_URL, offset=40)

    assert (first["limit"], first["total"], ids_of(first)) == (20, 22, newest_first(rides)[:20])
    assert past_end == {"items": [], "limit": 20, "offset": 40, "total": 22}


# Users -----------------------------------------------------------------------


async def test_admin_lists_users_newest_first(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    clock: ManualClock,
    admin_id: uuid.UUID,
) -> None:
    clock.advance(timedelta(minutes=1))
    pat = await ride_factory.passenger("pat")
    clock.advance(timedelta(minutes=1))
    dana = await driver_factory.driver("dana")
    await as_admin(client)

    body = await listing(client, ADMIN_USERS_URL)

    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [str(dana), str(pat), str(admin_id)]
    assert [item["role"] for item in body["items"]] == ["driver", "passenger", "admin"]
    assert all(set(item) == USER_FIELDS for item in body["items"])
    assert body["items"][1]["created_at"] == "2026-11-03T09:01:00Z"


async def test_users_with_the_same_creation_time_are_ordered_by_id(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    ids = [await ride_factory.passenger() for _ in range(4)]
    await as_admin(client)

    body = await listing(client, ADMIN_USERS_URL)

    expected = sorted([*ids, admin_id], key=lambda user_id: user_id.hex, reverse=True)
    assert [item["id"] for item in body["items"]] == [str(user_id) for user_id in expected]


async def test_user_shows_the_display_name_of_their_profile(
    client: httpx.AsyncClient, admin_id: uuid.UUID
) -> None:
    alice = await register_and_login(client, "alice")
    response = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "Alice A.", "phone": "+77011234567"},
        headers=alice.csrf_headers,
    )
    assert response.status_code == 200, response.text
    await register_and_login(client, "nobody")
    await as_admin(client)

    body = await listing(client, ADMIN_USERS_URL, role="passenger")

    names = {item["username"]: item["display_name"] for item in body["items"]}
    assert names == {"alice": "Alice A.", "nobody": None}


async def test_admin_filters_users_by_role(
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
    admin_id: uuid.UUID,
) -> None:
    await ride_factory.passenger("pat")
    dana = await driver_factory.driver("dana")
    await as_admin(client)

    drivers = await listing(client, ADMIN_USERS_URL, role="driver")
    admins = await listing(client, ADMIN_USERS_URL, role="admin")

    assert ([item["id"] for item in drivers["items"]], drivers["total"]) == ([str(dana)], 1)
    assert [item["username"] for item in admins["items"]] == ["admin"]


@pytest.mark.parametrize("params", [{"role": "root"}, {"limit": 101}, {"limit": 0}])
async def test_admin_user_parameters_are_validated(
    client: httpx.AsyncClient, admin_id: uuid.UUID, params: dict[str, Any]
) -> None:
    await as_admin(client)

    response = await client.get(ADMIN_USERS_URL, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_admin_user_pages(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    for _ in range(4):
        await ride_factory.passenger()
    await as_admin(client)

    page = await listing(client, ADMIN_USERS_URL, limit=2, offset=4)
    past_end = await listing(client, ADMIN_USERS_URL, limit=2, offset=10)

    assert (len(page["items"]), page["total"]) == (1, 5)
    assert past_end == {"items": [], "limit": 2, "offset": 10, "total": 5}


async def test_admin_lists_reveal_no_secrets(
    client: httpx.AsyncClient, ride_factory: RideFactory, admin_id: uuid.UUID
) -> None:
    alice = await register_and_login(client, "alice")
    await client.patch(
        "/api/v1/users/me", json={"phone": "+77017654321"}, headers=alice.csrf_headers
    )
    await ride_factory.searching_ride()
    admin = await login_as(client, "admin")
    session_token = client.cookies.get(SESSION_COOKIE)
    assert session_token

    texts = [(await client.get(url, params={"limit": 100})).text for url in ADMIN_URLS]

    for text in texts:
        for secret in ("password", "$argon2", "hash", "csrf", "token", "phone", "+7701"):
            assert secret not in text
        for value in (admin.csrf_token, alice.csrf_token, session_token):
            assert value not in text
        assert "route_geometry" not in text


# OpenAPI ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "parameters"),
    [
        (
            "/admin/rides",
            {"limit", "offset", "status", "created_from", "created_to"}
            | {"passenger_id", "driver_id"},
        ),
        ("/admin/users", {"limit", "offset", "role"}),
    ],
)
async def test_admin_lists_are_documented(
    client: httpx.AsyncClient, path: str, parameters: set[str]
) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    operation = paths[f"/api/v1{path}"]["get"]

    assert {item["name"] for item in operation["parameters"]} == parameters
    assert {"200", "401", "403", "422"} <= set(operation["responses"])
    assert {"SessionCookie": []} in operation["security"]
    assert set(paths[f"/api/v1{path}"]) == {"get"}
