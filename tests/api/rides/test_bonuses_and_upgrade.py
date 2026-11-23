"""Passenger bonuses (5 % back, at most half of a ride) and raising a searching ride's tariff."""

import uuid
from datetime import UTC, datetime

import httpx

from support.auth import register_and_login
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import NEAR_PICKUP, PASSENGER, send, trip_in
from support.payments import stored_payment
from support.rides import RIDES_URL, request_quote, ride_body, ride_headers, ride_url
from taxi_service.database.session import SessionFactory
from taxi_service.modules.bonuses.models import BonusWallet
from taxi_service.modules.rides.tariffs import Tariff

BONUSES_URL = "/api/v1/bonuses/me"


async def give_bonuses(session_factory: SessionFactory, user_id: uuid.UUID, amount: int) -> None:
    async with session_factory() as session, session.begin():
        session.add(BonusWallet(user_id=user_id, balance_kzt=amount, updated_at=datetime.now(UTC)))


async def balance(client: httpx.AsyncClient) -> int:
    await login_as(client, PASSENGER)
    response = await client.get(BONUSES_URL)
    assert response.status_code == 200, response.text
    value: int = response.json()["balance_kzt"]
    return value


async def order(client: httpx.AsyncClient, *, use_bonus: bool) -> dict[str, object]:
    passenger = await login_as(client, PASSENGER)
    quote = await request_quote(client, passenger)
    body = {**ride_body(quote["quote_id"]), "use_bonus": use_bonus}
    response = await client.post(RIDES_URL, json=body, headers=ride_headers(passenger))
    assert response.status_code == 201, response.text
    ride: dict[str, object] = response.json()
    return ride


async def upgrade(
    client: httpx.AsyncClient, ride_id: object, tariff: str, *, use_bonus: bool = False
) -> httpx.Response:
    passenger = await login_as(client, PASSENGER)
    return await client.post(
        f"{ride_url(str(ride_id))}/upgrade",
        json={"tariff": tariff, "use_bonus": use_bonus},
        headers=passenger.csrf_headers,
    )


async def test_completed_ride_earns_five_percent_of_its_price(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await trip_in("completed", client, driver_factory, dispatcher)

    assert await balance(client) == 110  # 5 % of the 2200 KZT economy ride


async def test_bonuses_pay_at_most_half_and_return_after_cancel(
    client: httpx.AsyncClient, driver_factory: DriverFactory, session_factory: SessionFactory
) -> None:
    await driver_factory.driver("dana", location=NEAR_PICKUP)
    passenger = await register_and_login(client, PASSENGER)
    await give_bonuses(session_factory, passenger.id, 5000)

    ride = await order(client, use_bonus=True)

    assert ride["status"] == "searching"
    assert ride["bonus_kzt"] == 1100
    payment = await stored_payment(session_factory, uuid.UUID(str(ride["id"])))
    assert payment is not None
    assert payment.amount_kzt == 1100
    assert await balance(client) == 3900

    response = await send(client, str(ride["id"]), "cancel", PASSENGER)
    assert response.status_code == 200, response.text
    assert await balance(client) == 5000


async def test_upgrade_reprices_the_ride_and_searches_the_new_class(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    comfort_driver = await driver_factory.driver(
        "cara", location=NEAR_PICKUP, car_class=Tariff.COMFORT
    )

    options = (await client.get(f"{ride_url(trip.ride_id)}/upgrades")).json()
    assert [option["tariff"] for option in options["options"]] == [
        "comfort",
        "comfort_plus",
        "business",
    ]
    assert options["options"][0]["surcharge_kzt"] == 725

    response = await upgrade(client, trip.ride_id, "comfort")

    assert response.status_code == 200, response.text
    assert (response.json()["tariff"], response.json()["amount_kzt"]) == ("comfort", 2925)
    payment = await stored_payment(session_factory, trip.ride_id)
    assert payment is not None
    assert payment.amount_kzt == 2925
    pending = await dispatcher.pending(trip.ride_id)
    assert pending is not None
    assert pending.driver_id == comfort_driver

    lower = await upgrade(client, trip.ride_id, "economy")
    assert lower.status_code == 409
    assert lower.json()["error"]["code"] == "tariff_not_higher"


async def test_upgrade_surcharge_can_be_paid_with_bonuses(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    await give_bonuses(session_factory, trip.passenger_id, 1000)

    response = await upgrade(client, trip.ride_id, "comfort", use_bonus=True)

    assert response.status_code == 200, response.text
    assert response.json()["bonus_kzt"] == 1000
    payment = await stored_payment(session_factory, trip.ride_id)
    assert payment is not None
    assert payment.amount_kzt == 1925


async def test_upgrade_is_refused_once_a_driver_accepted(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)

    late = await upgrade(client, trip.ride_id, "comfort")
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "ride_upgrade_unavailable"
