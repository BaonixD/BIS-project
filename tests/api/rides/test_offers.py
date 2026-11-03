"""Offers through the API: search on ride creation, the driver's list, accept and reject.

POST /rides asks the nearest driver at once; GET /drivers/me/offers shows the
driver's open offer; POST /ride-offers/{id}/accept assigns the ride, /reject
passes it to the next candidate (MVP_SPEC §6, §8).
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest

from support.auth import CSRF_HEADER, LoggedInUser, register_and_login
from support.clock import ManualClock
from support.dispatch import OFFERS_URL, Dispatcher, accept_url, reject_url
from support.drivers import DriverFactory, login_as
from support.rides import (
    ABAY_DOSTYK,
    AL_FARABI,
    RIDES_URL,
    order_ride,
    request_quote,
    ride_headers,
    ride_url,
)
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides import dispatch
from taxi_service.modules.rides.states import OfferStatus

NEAR_PICKUP = Coordinates(longitude=76.9580, latitude=43.2389)
FARTHER = Coordinates(longitude=76.9650, latitude=43.2389)
TTL = timedelta(seconds=30)


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def passenger_with_ride(client: httpx.AsyncClient) -> tuple[LoggedInUser, dict[str, Any]]:
    passenger = await register_and_login(client, "pat")
    return passenger, await order_ride(client, passenger)


async def open_offers(client: httpx.AsyncClient, username: str) -> list[dict[str, Any]]:
    await login_as(client, username)
    response = await client.get(OFFERS_URL)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def answer(
    client: httpx.AsyncClient, url: str, username: str, *, csrf: bool = True
) -> httpx.Response:
    user = await login_as(client, username)
    return await client.post(url, headers=user.csrf_headers if csrf else {})


# Search on creation


async def test_new_ride_is_offered_to_the_nearest_driver_at_once(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    await driver_factory.driver("farther", location=FARTHER)
    near = await driver_factory.driver("near", location=NEAR_PICKUP)

    _, ride = await passenger_with_ride(client)

    assert (ride["status"], ride["driver_id"]) == ("searching", None)
    [offer] = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert (offer.driver_id, offer.status, offer.expires_at) == (
        near,
        OfferStatus.PENDING,
        clock.now() + TTL,
    )


async def test_without_drivers_the_new_ride_has_no_driver(
    client: httpx.AsyncClient, dispatcher: Dispatcher
) -> None:
    _, ride = await passenger_with_ride(client)

    assert (ride["status"], ride["driver_id"]) == ("no_driver", None)
    assert await dispatcher.offers(uuid.UUID(ride["id"])) == []


async def test_after_no_driver_the_passenger_can_order_again(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    passenger, first = await passenger_with_ride(client)
    await driver_factory.driver("driver", location=NEAR_PICKUP)

    second = await order_ride(client, passenger)

    assert (first["status"], second["status"]) == ("no_driver", "searching")


async def test_replaying_the_creation_does_not_search_again(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    headers = {**passenger.csrf_headers, "Idempotency-Key": "key-1"}
    first = await client.post(RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=headers)
    await driver_factory.driver("late", location=NEAR_PICKUP)

    replay = await client.post(RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=headers)

    assert (first.status_code, replay.status_code) == (201, 201)
    assert replay.json()["status"] == "no_driver"
    assert await dispatcher.offers(uuid.UUID(first.json()["id"])) == []


async def test_a_failing_first_search_step_still_returns_the_searching_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ride is committed before the step; the loop takes it up later."""
    await driver_factory.driver("near", location=NEAR_PICKUP)

    async def broken_step(*args: object) -> None:
        raise RuntimeError("search step failed")

    with monkeypatch.context() as patch:
        patch.setattr(dispatch, "_step", broken_step)
        passenger = await register_and_login(client, "pat")
        quote = await request_quote(client, passenger)
        response = await client.post(
            RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=ride_headers(passenger)
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["driver_id"]) == ("searching", None)
    assert await dispatcher.offers(uuid.UUID(body["id"])) == []
    assert await dispatcher.process_due() == 1
    assert len(await dispatcher.offers(uuid.UUID(body["id"]))) == 1


# The driver's offers


async def test_driver_sees_the_open_offer_with_the_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, clock: ManualClock
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    _, ride = await passenger_with_ride(client)

    await login_as(client, "near")
    response = await client.get(OFFERS_URL)

    assert response.status_code == 200
    body = response.json()
    assert (body["limit"], body["offset"], body["total"]) == (20, 0, 1)
    [offer] = body["items"]
    assert set(offer) == {
        "id",
        "ride_id",
        "status",
        "pickup",
        "dropoff",
        "distance_m",
        "duration_s",
        "amount_kzt",
        "currency",
        "tariff",
        "created_at",
        "expires_at",
    }
    assert (offer["ride_id"], offer["status"]) == (ride["id"], "pending")
    assert (offer["pickup"], offer["dropoff"]) == (ABAY_DOSTYK, AL_FARABI)
    assert (offer["distance_m"], offer["duration_s"]) == (10_000, 1_500)
    assert (offer["amount_kzt"], offer["currency"], offer["tariff"]) == (2200, "KZT", "economy")
    assert datetime.fromisoformat(offer["expires_at"]) == clock.now() + TTL


async def test_other_drivers_do_not_see_the_offer(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await driver_factory.driver("other", location=FARTHER, online=False)
    await passenger_with_ride(client)

    assert await open_offers(client, "other") == []


async def test_an_offer_past_its_deadline_is_not_listed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, clock: ManualClock
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await passenger_with_ride(client)
    clock.advance(TTL)  # the loop has not marked it yet

    assert await open_offers(client, "near") == []


async def test_offers_are_for_drivers_only(client: httpx.AsyncClient) -> None:
    assert (await client.get(OFFERS_URL)).status_code == 401
    await register_and_login(client, "pat")

    response = await client.get(OFFERS_URL)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# Accept


async def test_accept_assigns_the_ride_to_the_driver(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    driver = await driver_factory.driver("near", location=NEAR_PICKUP)
    _, ride = await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")

    response = await answer(client, accept_url(offer["id"]), "near")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["status"], body["driver_id"]) == (ride["id"], "assigned", str(driver))
    assert (await client.get(ride_url(ride["id"]))).json()["status"] == "assigned"
    assert await open_offers(client, "near") == []


async def test_accepting_again_returns_the_same_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, clock: ManualClock
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")
    first = await answer(client, accept_url(offer["id"]), "near")
    clock.advance(timedelta(minutes=2))

    again = await answer(client, accept_url(offer["id"]), "near")

    assert again.status_code == 200
    assert again.json() == first.json()


async def test_accept_at_the_deadline_is_a_conflict(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    _, ride = await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")
    clock.advance(TTL)

    response = await answer(client, accept_url(offer["id"]), "near")

    assert response.status_code == 409
    assert error_code(response) == "offer_expired"
    [stored] = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert stored.status is OfferStatus.EXPIRED


async def test_another_drivers_offer_is_not_found(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await driver_factory.driver("other", location=FARTHER, online=False)
    _, ride = await passenger_with_ride(client)
    [offer] = await dispatcher.offers(uuid.UUID(ride["id"]))

    for url in (accept_url(offer.id), reject_url(offer.id), accept_url(uuid.uuid4())):
        response = await answer(client, url, "other")
        assert response.status_code == 404
        assert error_code(response) == "offer_not_found"
    [stored] = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert stored.status is OfferStatus.PENDING


async def test_answers_need_the_csrf_token(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")

    for url in (accept_url(offer["id"]), reject_url(offer["id"])):
        response = await client.post(url, headers={CSRF_HEADER: "wrong"})
        assert response.status_code == 403
        assert error_code(response) == "csrf_failed"


async def test_a_passenger_cannot_answer_offers(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    passenger, ride = await passenger_with_ride(client)
    [offer] = await dispatcher.offers(uuid.UUID(ride["id"]))

    response = await client.post(accept_url(offer.id), headers=passenger.csrf_headers)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# Reject


async def test_reject_passes_the_ride_to_the_next_driver(
    client: httpx.AsyncClient, driver_factory: DriverFactory, clock: ManualClock
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await driver_factory.driver("farther", location=FARTHER)
    _, ride = await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")
    clock.advance(timedelta(seconds=3))

    response = await answer(client, reject_url(offer["id"]), "near")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["status"]) == (offer["id"], "rejected")
    [following] = await open_offers(client, "farther")
    assert following["ride_id"] == ride["id"]


async def test_reject_after_accept_is_a_conflict(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.driver("near", location=NEAR_PICKUP)
    await passenger_with_ride(client)
    [offer] = await open_offers(client, "near")
    await answer(client, accept_url(offer["id"]), "near")

    response = await answer(client, reject_url(offer["id"]), "near")

    assert response.status_code == 409
    assert error_code(response) == "invalid_offer_transition"


# OpenAPI


@pytest.mark.parametrize(
    ("method", "path", "statuses"),
    [
        ("get", "/drivers/me/offers", {"401", "403"}),
        ("post", "/ride-offers/{offer_id}/accept", {"401", "403", "404", "409"}),
        ("post", "/ride-offers/{offer_id}/reject", {"401", "403", "404", "409"}),
    ],
)
async def test_offer_routes_are_documented(
    client: httpx.AsyncClient, method: str, path: str, statuses: set[str]
) -> None:
    schema = (await client.get("/openapi.json")).json()

    operation = schema["paths"][f"/api/v1{path}"][method]

    assert statuses <= set(operation["responses"])
