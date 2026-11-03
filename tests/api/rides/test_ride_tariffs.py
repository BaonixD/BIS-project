"""Tariffs of a ride (ADR 0012): chosen with the order, priced by the quote, served by a class."""

import uuid
from typing import Any

import httpx
from fastapi import FastAPI

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import OFFERS_URL, Dispatcher
from support.drivers import DriverFactory, create_admin, login_as
from support.history import ADMIN_RIDES_URL, get_page
from support.lifecycle import NEAR_PICKUP
from support.payments import stored_payment
from support.rides import RIDES_URL, order_ride, request_quote, ride_body, ride_headers, ride_url
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.tariffs import Tariff

REPLAY_HEADER = "Idempotent-Replayed"


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


def option_amount(quote: dict[str, Any], tariff: str) -> int:
    amounts = [option["amount_kzt"] for option in quote["options"] if option["tariff"] == tariff]
    assert len(amounts) == 1
    return int(amounts[0])


async def test_ride_costs_the_quoted_price_of_its_tariff(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], tariff="comfort"),
        headers=ride_headers(passenger),
    )

    assert response.status_code == 201, response.text
    ride = response.json()
    assert (ride["tariff"], ride["amount_kzt"]) == ("comfort", option_amount(quote, "comfort"))
    assert ride["amount_kzt"] == 2925
    payment = await stored_payment(session_factory, uuid.UUID(ride["id"]))
    assert payment is not None
    assert payment.amount_kzt == 2925


async def test_omitted_tariff_is_economy(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")

    ride = await order_ride(client, passenger)

    assert (ride["tariff"], ride["amount_kzt"]) == ("economy", 2200)


async def test_omitted_tariff_repeats_as_explicit_economy(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    first = await client.post(
        RIDES_URL, json=ride_body(quote["quote_id"]), headers=ride_headers(passenger, "key-1")
    )

    repeat = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], tariff="economy"),
        headers=ride_headers(passenger, "key-1"),
    )

    assert (first.status_code, repeat.status_code) == (201, 201)
    assert repeat.headers[REPLAY_HEADER] == "true"
    assert repeat.json()["id"] == first.json()["id"]


async def test_same_key_with_another_tariff_is_a_conflict(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    await client.post(
        RIDES_URL, json=ride_body(quote["quote_id"]), headers=ride_headers(passenger, "key-1")
    )

    response = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], tariff="business"),
        headers=ride_headers(passenger, "key-1"),
    )

    assert response.status_code == 409
    assert error_code(response) == "idempotency_key_reused"


async def test_tariff_is_shown_in_details_history_and_admin_list(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    await create_admin(app, session_factory, clock)
    passenger = await register_and_login(client, "pat")
    ride = await order_ride(client, passenger, tariff="comfort_plus")

    details = (await client.get(ride_url(ride["id"]))).json()
    [mine] = (await get_page(client, RIDES_URL))["items"]
    await login_as(client, "admin")
    [listed] = (await get_page(client, ADMIN_RIDES_URL))["items"]

    assert details["tariff"] == mine["tariff"] == listed["tariff"] == "comfort_plus"
    assert details["amount_kzt"] == mine["amount_kzt"] == listed["amount_kzt"] == 3650


async def test_offer_goes_to_a_driver_of_a_high_enough_class(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("economy_near", location=NEAR_PICKUP)
    business = await driver_factory.driver(
        "business_near", location=NEAR_PICKUP, car_class=Tariff.BUSINESS
    )
    passenger = await register_and_login(client, "pat")

    ride = await order_ride(client, passenger, tariff="comfort")

    offer = await dispatcher.pending(uuid.UUID(ride["id"]))
    assert offer is not None
    assert offer.driver_id == business
    await login_as(client, "business_near")
    [shown] = (await get_page(client, OFFERS_URL))["items"]
    assert (shown["tariff"], shown["amount_kzt"]) == ("comfort", 2925)


async def test_no_driver_when_every_nearby_car_is_below_the_tariff(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("economy_near", location=NEAR_PICKUP)
    await driver_factory.driver("comfort_near", location=NEAR_PICKUP, car_class=Tariff.COMFORT)
    passenger = await register_and_login(client, "pat")

    ride = await order_ride(client, passenger, tariff="business")

    assert ride["status"] == "no_driver"
    assert await dispatcher.offers(uuid.UUID(ride["id"])) == []
