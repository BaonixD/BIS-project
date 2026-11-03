"""POST /rides/{ride_id}/rating (ADR 0013): the participants rate each other after the trip.

The passenger is ``pat``, the driver ``dana`` (``support.lifecycle``).
"""

import asyncio
import dataclasses
import uuid
from datetime import datetime
from typing import Any

import httpx
import pytest

from support.auth import register_and_login
from support.dispatch import OFFERS_URL, Dispatcher, accept_url
from support.drivers import DRIVERS_ME_URL, DriverFactory, login_as
from support.lifecycle import Trip, expect_ok, trip_in
from support.rides import order_ride, ride_url
from taxi_service.modules.ratings import records as ratings_records

ME_URL = "/api/v1/users/me"
NO_RATING = {"average": None, "count": 0}


def rating_url(ride_id: uuid.UUID | str) -> str:
    return f"{ride_url(ride_id)}/rating"


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def rate(
    client: httpx.AsyncClient, ride_id: uuid.UUID | str, username: str, body: dict[str, Any]
) -> httpx.Response:
    user = await login_as(client, username)
    return await client.post(rating_url(ride_id), json=body, headers=user.csrf_headers)


async def expect_rated(
    client: httpx.AsyncClient, ride_id: uuid.UUID | str, username: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await rate(client, ride_id, username, body)
    assert response.status_code == 201, response.text
    rated: dict[str, Any] = response.json()
    return rated


async def read_as(client: httpx.AsyncClient, url: str, username: str) -> dict[str, Any]:
    await login_as(client, username)
    response = await client.get(url)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> Trip:
    return await trip_in("completed", client, driver_factory, dispatcher)


async def next_trip(client: httpx.AsyncClient, dispatcher: Dispatcher, trip: Trip) -> str:
    """``pat`` orders again and ``dana`` accepts: the new ride is assigned."""
    passenger = await login_as(client, trip.passenger)
    ride = await order_ride(client, passenger)
    offer = await dispatcher.pending(uuid.UUID(ride["id"]))
    assert offer is not None
    driver = await login_as(client, trip.driver)
    accepted = await client.post(accept_url(offer.id), headers=driver.csrf_headers)
    assert accepted.status_code == 200, accepted.text
    ride_id: str = ride["id"]
    return ride_id


# Rating


async def test_passenger_rates_the_driver(client: httpx.AsyncClient, completed: Trip) -> None:
    body = await expect_rated(
        client,
        completed.ride_id,
        completed.passenger,
        {"stars": 5, "tags": ["polite", "clean_car"], "comment": "  Great ride  "},
    )

    assert set(body) == {"ride_id", "rater_role", "stars", "tags", "comment", "created_at"}
    assert (body["ride_id"], body["rater_role"], body["stars"]) == (
        str(completed.ride_id),
        "passenger",
        5,
    )
    assert (body["tags"], body["comment"]) == (["polite", "clean_car"], "Great ride")
    assert datetime.fromisoformat(body["created_at"])


async def test_driver_rates_the_passenger(client: httpx.AsyncClient, completed: Trip) -> None:
    body = await expect_rated(
        client, completed.ride_id, completed.driver, {"stars": 4, "tags": ["on_time"]}
    )

    assert (body["rater_role"], body["stars"], body["tags"], body["comment"]) == (
        "driver",
        4,
        ["on_time"],
        None,
    )


async def test_tags_are_unique_in_a_fixed_order(client: httpx.AsyncClient, completed: Trip) -> None:
    body = await expect_rated(
        client,
        completed.ride_id,
        completed.passenger,
        {"stars": 5, "tags": ["knows_route", "polite", "knows_route", "smooth_driving"]},
    )

    assert body["tags"] == ["polite", "smooth_driving", "knows_route"]


@pytest.mark.parametrize("body", [{"stars": 3}, {"stars": 3, "tags": [], "comment": "   "}])
async def test_tags_and_comment_are_optional(
    client: httpx.AsyncClient, completed: Trip, body: dict[str, Any]
) -> None:
    rated = await expect_rated(client, completed.ride_id, completed.passenger, body)

    assert (rated["stars"], rated["tags"], rated["comment"]) == (3, [], None)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"stars": 0},
        {"stars": 6},
        {"stars": 4.5},
        {"stars": "5"},
        {"stars": None},
        {"stars": 5, "tags": ["rude"]},
        {"stars": 5, "tags": "polite"},
        {"stars": 5, "comment": "x" * 501},
        {"stars": 5, "comment": "bad\x00text"},
        {"stars": 5, "ratee_id": str(uuid.uuid4())},
    ],
)
async def test_invalid_rating_is_rejected(
    client: httpx.AsyncClient, completed: Trip, body: dict[str, Any]
) -> None:
    response = await rate(client, completed.ride_id, completed.passenger, body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_comment_of_500_characters_is_accepted(
    client: httpx.AsyncClient, completed: Trip
) -> None:
    rated = await expect_rated(
        client, completed.ride_id, completed.passenger, {"stars": 5, "comment": "x" * 500}
    )

    assert len(rated["comment"]) == 500


@pytest.mark.parametrize(
    ("rater", "tag"),
    [("passenger", "on_time"), ("passenger", "clean"), ("driver", "clean_car")],
)
async def test_each_side_has_its_own_tags(
    client: httpx.AsyncClient, completed: Trip, rater: str, tag: str
) -> None:
    username = completed.passenger if rater == "passenger" else completed.driver

    response = await rate(client, completed.ride_id, username, {"stars": 5, "tags": [tag]})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    [error] = response.json()["error"]["details"]["errors"]
    assert error["loc"][:2] == ["body", "tags"]


@pytest.mark.parametrize("status", ["searching", "assigned", "arrived", "in_progress", "cancelled"])
async def test_only_a_completed_ride_is_rated(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    response = await rate(client, trip.ride_id, trip.passenger, {"stars": 5})

    assert response.status_code == 409
    assert error_code(response) == "ride_not_completed"


async def test_rating_twice_is_a_conflict(client: httpx.AsyncClient, completed: Trip) -> None:
    first = await expect_rated(client, completed.ride_id, completed.passenger, {"stars": 2})

    response = await rate(client, completed.ride_id, completed.passenger, {"stars": 5})

    assert response.status_code == 409
    assert error_code(response) == "rating_already_exists"
    shown = await read_as(client, ride_url(completed.ride_id), completed.passenger)
    assert shown["my_rating"] == {"stars": first["stars"], "tags": [], "comment": None}


async def test_concurrent_ratings_store_one(
    client: httpx.AsyncClient, other_client: httpx.AsyncClient, completed: Trip
) -> None:
    first = await login_as(client, completed.passenger)
    second = await login_as(other_client, completed.passenger)

    responses = await asyncio.gather(
        client.post(rating_url(completed.ride_id), json={"stars": 5}, headers=first.csrf_headers),
        other_client.post(
            rating_url(completed.ride_id), json={"stars": 1}, headers=second.csrf_headers
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    [conflict] = [response for response in responses if response.status_code == 409]
    assert error_code(conflict) == "rating_already_exists"


async def test_lost_race_is_decided_by_the_unique_constraint(
    client: httpx.AsyncClient, completed: Trip, monkeypatch: pytest.MonkeyPatch
) -> None:
    await expect_rated(client, completed.ride_id, completed.passenger, {"stars": 5})

    async def stale_check(*args: Any, **kwargs: Any) -> None:
        # What a concurrent transaction on PostgreSQL could see before the winner commits.
        return None

    monkeypatch.setattr(ratings_records, "rating_of_side", stale_check)

    response = await rate(client, completed.ride_id, completed.passenger, {"stars": 1})

    assert response.status_code == 409
    assert error_code(response) == "rating_already_exists"


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_rate(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip, role: str
) -> None:
    if role == "driver":
        await driver_factory.driver("other_driver")
        username = "other_driver"
    else:
        await register_and_login(client, "other_passenger")
        username = "other_passenger"

    response = await rate(client, completed.ride_id, username, {"stars": 1})

    assert response.status_code == 404
    assert error_code(response) == "ride_not_found"


async def test_unknown_ride_is_not_found(client: httpx.AsyncClient, completed: Trip) -> None:
    response = await rate(client, uuid.uuid4(), completed.passenger, {"stars": 5})

    assert response.status_code == 404
    assert error_code(response) == "ride_not_found"


async def test_admin_cannot_rate(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip
) -> None:
    await driver_factory.admin_id()

    response = await rate(client, completed.ride_id, "admin", {"stars": 5})

    assert response.status_code == 403
    assert error_code(response) == "rating_forbidden"


async def test_rating_needs_the_csrf_token(client: httpx.AsyncClient, completed: Trip) -> None:
    await login_as(client, completed.passenger)

    response = await client.post(rating_url(completed.ride_id), json={"stars": 5})

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


# What the ride shows


async def test_ride_shows_only_the_viewers_own_rating(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip
) -> None:
    url = ride_url(completed.ride_id)
    assert (await read_as(client, url, completed.passenger))["my_rating"] is None

    await expect_rated(
        client,
        completed.ride_id,
        completed.passenger,
        {"stars": 4, "tags": ["polite"], "comment": "ok"},
    )

    mine = await read_as(client, url, completed.passenger)
    assert mine["my_rating"] == {"stars": 4, "tags": ["polite"], "comment": "ok"}
    assert (await read_as(client, url, completed.driver))["my_rating"] is None
    await driver_factory.admin_id()
    assert (await read_as(client, url, "admin"))["my_rating"] is None


async def test_averages_of_both_sides(
    client: httpx.AsyncClient, dispatcher: Dispatcher, completed: Trip
) -> None:
    await expect_rated(client, completed.ride_id, completed.passenger, {"stars": 4})
    await expect_rated(client, completed.ride_id, completed.driver, {"stars": 3})
    second = await next_trip(client, dispatcher, completed)
    for command in ("arrive", "start", "complete"):
        await expect_ok(client, dataclasses.replace(completed, ride_id=uuid.UUID(second)), command)
    await expect_rated(client, second, completed.passenger, {"stars": 5})

    driver = await read_as(client, DRIVERS_ME_URL, completed.driver)
    assert driver["rating"] == {"average": 4.5, "count": 2}
    assert (await read_as(client, ME_URL, completed.driver))["rating"] == driver["rating"]
    passenger = await read_as(client, ME_URL, completed.passenger)
    assert passenger["rating"] == {"average": 3.0, "count": 1}


async def test_new_accounts_have_no_rating(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await register_and_login(client, "pat")
    assert (await client.get(ME_URL)).json()["rating"] == NO_RATING
    await driver_factory.driver("dana")
    assert (await read_as(client, DRIVERS_ME_URL, "dana"))["rating"] == NO_RATING


async def test_driver_card_and_offer_show_the_other_sides_rating(
    client: httpx.AsyncClient, dispatcher: Dispatcher, completed: Trip
) -> None:
    await expect_rated(client, completed.ride_id, completed.passenger, {"stars": 4})
    await expect_rated(client, completed.ride_id, completed.driver, {"stars": 2})
    passenger = await login_as(client, completed.passenger)

    ride = await order_ride(client, passenger)

    [offer] = (await read_as(client, OFFERS_URL, completed.driver))["items"]
    assert offer["passenger_rating"] == {"average": 2.0, "count": 1}
    accepted = await client.post(
        accept_url(offer["id"]), headers=(await login_as(client, completed.driver)).csrf_headers
    )
    assert accepted.status_code == 200, accepted.text
    card = (await read_as(client, ride_url(ride["id"]), completed.passenger))["driver"]
    assert card["rating"] == {"average": 4.0, "count": 1}
