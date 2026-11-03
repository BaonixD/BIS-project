"""Payment of a completed ride: the passenger picks cash or Kaspi and presses "Paid".

Kaspi is on with ``TEST_KASPI_URL``; no request leaves the test process and no
real payment is made. Passenger ``pat``, driver ``dana``, admin ``admin``.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import Trip, trip_in
from support.payments import (
    ADMIN,
    TEST_KASPI_URL,
    expect_paid_ok,
    kaspi_on,
    pay,
    payment_url,
    read_payment,
    stored_payment,
)
from support.rows import insert_driver, insert_payment, insert_ride
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.config import PaymentSettings

KASPI = {"method": "kaspi_link"}
CASH = {"method": "cash"}


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


@pytest.fixture
async def completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> Trip:
    """A completed trip of ``pat`` with ``dana``; the admin account exists."""
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    await driver_factory.admin_id()
    return trip


async def stranger(client: httpx.AsyncClient, driver_factory: DriverFactory, role: str) -> str:
    """Another passenger or driver who has nothing to do with the trip."""
    if role == "driver":
        await driver_factory.driver("other_driver")
        return "other_driver"
    await register_and_login(client, "other_passenger")
    return "other_passenger"


def expect_error(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == code
    return body


def paid_at(body: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(body["paid_at"])


async def expect_unpaid_cash(session_factory: SessionFactory, ride_id: uuid.UUID) -> None:
    stored = await stored_payment(session_factory, ride_id)
    assert stored is not None
    assert (stored.method, stored.status, stored.paid_at) == ("cash", "unpaid", None)


# Reading


async def test_passenger_sees_an_unpaid_cash_payment_after_completion(
    client: httpx.AsyncClient, completed: Trip
) -> None:
    body = await read_payment(client, completed.ride_id, completed.passenger)

    assert body == {
        "ride_id": str(completed.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": "cash",
        "status": "unpaid",
        "paid_at": None,
        "payment_url": None,
    }


@pytest.mark.parametrize("username", ["dana", ADMIN])
async def test_driver_and_admin_see_the_payment(
    client: httpx.AsyncClient, completed: Trip, username: str
) -> None:
    body = await read_payment(client, completed.ride_id, username)

    assert (body["status"], body["method"], body["amount_kzt"]) == ("unpaid", "cash", 2200)


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_does_not_see_the_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip, role: str
) -> None:
    username = await stranger(client, driver_factory, role)
    await login_as(client, username)

    expect_error(await client.get(payment_url(completed.ride_id)), 404, "ride_not_found")


async def test_unknown_ride_has_no_payment(client: httpx.AsyncClient, completed: Trip) -> None:
    await login_as(client, completed.passenger)

    expect_error(await client.get(payment_url(uuid.uuid4())), 404, "ride_not_found")


async def test_payment_needs_a_session(client: httpx.AsyncClient, completed: Trip) -> None:
    client.cookies.clear()

    expect_error(await client.get(payment_url(completed.ride_id)), 401, "not_authenticated")


@pytest.mark.parametrize("status", ["assigned", "in_progress", "cancelled"])
async def test_no_payment_before_the_ride_is_completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    await login_as(client, trip.passenger)

    expect_error(await client.get(payment_url(trip.ride_id)), 409, "ride_not_completed")


# Paying


async def test_passenger_pays_cash_and_it_counts_at_once(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    body = await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)

    assert body == {
        "ride_id": str(completed.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": "cash",
        "status": "paid",
        "paid_at": body["paid_at"],
        "payment_url": None,
    }
    assert paid_at(body) == clock.now()
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.status, stored.paid_at, stored.updated_at) == ("paid", clock.now(), clock.now())
    for username in (completed.driver, ADMIN):
        assert (await read_payment(client, completed.ride_id, username))["status"] == "paid"


async def test_repeated_pay_answers_the_same_payment(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    first = await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)
    clock.advance(timedelta(minutes=5))

    again = await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)

    assert again == first
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.paid_at == stored.updated_at == paid_at(first)


async def test_passenger_pays_by_kaspi_link(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    switched = await expect_paid_ok(
        client, completed.ride_id, "method", completed.passenger, json=KASPI
    )
    shown = await read_payment(client, completed.ride_id, completed.passenger)

    body = await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)

    assert (switched["method"], switched["status"]) == ("kaspi_link", "unpaid")
    assert switched["payment_url"] == shown["payment_url"] == TEST_KASPI_URL
    assert (body["method"], body["status"], body["payment_url"]) == (
        "kaspi_link",
        "paid",
        TEST_KASPI_URL,
    )
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.method, stored.status, stored.amount_kzt) == ("kaspi_link", "paid", 2200)


@pytest.mark.parametrize("username", ["dana", ADMIN])
async def test_only_the_passenger_pays(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory, username: str
) -> None:
    response = await pay(client, completed.ride_id, "pay", username)

    body = expect_error(response, 403, "payment_action_forbidden")
    assert body["error"]["details"] == {"action": "pay"}
    await expect_unpaid_cash(session_factory, completed.ride_id)


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_pay(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    session_factory: SessionFactory,
    role: str,
) -> None:
    username = await stranger(client, driver_factory, role)

    expect_error(await pay(client, completed.ride_id, "pay", username), 404, "ride_not_found")
    await expect_unpaid_cash(session_factory, completed.ride_id)


async def test_pay_for_an_unknown_ride(client: httpx.AsyncClient, completed: Trip) -> None:
    response = await pay(client, uuid.uuid4(), "pay", completed.passenger)

    expect_error(response, 404, "ride_not_found")


async def test_passenger_cannot_pay_before_completion(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    expect_error(await pay(client, trip.ride_id, "pay", trip.passenger), 409, "ride_not_completed")


async def test_a_body_cannot_change_what_is_paid(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    body = await expect_paid_ok(
        client,
        completed.ride_id,
        "pay",
        completed.passenger,
        json={"amount_kzt": 1, "method": "kaspi_link"},
    )

    assert (body["amount_kzt"], body["method"]) == (2200, "cash")
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.amount_kzt, stored.method, stored.status) == (2200, "cash", "paid")


async def test_concurrent_pays_record_one_payment(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    first = await login_as(client, completed.passenger)
    second = await login_as(other_client, completed.passenger)
    url = payment_url(completed.ride_id, "pay")

    responses = await asyncio.gather(
        client.post(url, headers=first.csrf_headers),
        other_client.post(url, headers=second.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.status == "paid"


async def test_pay_against_switch_to_kaspi(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    first = await login_as(client, completed.passenger)
    second = await login_as(other_client, completed.passenger)

    paid, switched = await asyncio.gather(
        client.post(payment_url(completed.ride_id, "pay"), headers=first.csrf_headers),
        other_client.put(
            payment_url(completed.ride_id, "method"), json=KASPI, headers=second.csrf_headers
        ),
    )

    assert paid.status_code == 200, paid.text
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.status == "paid"
    if switched.status_code == 200:  # the switch came first, then the payment
        assert paid.json()["method"] == stored.method == "kaspi_link"
    else:  # the payment came first: the method is final
        expect_error(switched, 409, "invalid_payment_transition")
        assert paid.json()["method"] == stored.method == "cash"


async def test_paying_one_ride_leaves_other_rides_alone(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    other_ride = await insert_ride(
        session_factory, status="completed", driver_id=await insert_driver(session_factory)
    )
    await insert_payment(session_factory, other_ride)

    await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)

    await expect_unpaid_cash(session_factory, uuid.UUID(other_ride))


# Choosing the method


async def test_choosing_the_current_method_again_changes_nothing(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    before = await stored_payment(session_factory, completed.ride_id)

    body = await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=CASH)

    assert (body["method"], body["status"], body["payment_url"]) == ("cash", "unpaid", None)
    assert await stored_payment(session_factory, completed.ride_id) == before


async def test_back_to_cash_hides_the_link(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)

    body = await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=CASH)

    assert (body["method"], body["status"], body["payment_url"]) == ("cash", "unpaid", None)
    await expect_unpaid_cash(session_factory, completed.ride_id)


@pytest.mark.parametrize("payload", [KASPI, CASH])
async def test_method_cannot_change_after_payment(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    payload: dict[str, str],
) -> None:
    await expect_paid_ok(client, completed.ride_id, "pay", completed.passenger)

    response = await pay(client, completed.ride_id, "method", completed.passenger, json=payload)

    body = expect_error(response, 409, "invalid_payment_transition")
    assert body["error"]["details"] == {"action": "change_method", "status": "paid"}
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.method, stored.status) == ("cash", "paid")


@pytest.mark.parametrize("username", ["dana", ADMIN])
async def test_only_the_passenger_chooses_the_method(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory, username: str
) -> None:
    response = await pay(client, completed.ride_id, "method", username, json=KASPI)

    body = expect_error(response, 403, "payment_action_forbidden")
    assert body["error"]["details"] == {"action": "change_method"}
    await expect_unpaid_cash(session_factory, completed.ride_id)


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_choose_the_method(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip, role: str
) -> None:
    username = await stranger(client, driver_factory, role)

    response = await pay(client, completed.ride_id, "method", username, json=KASPI)

    expect_error(response, 404, "ride_not_found")


async def test_method_cannot_be_chosen_before_completion(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    response = await pay(client, trip.ride_id, "method", trip.passenger, json=KASPI)

    expect_error(response, 409, "ride_not_completed")


@pytest.mark.parametrize(
    "payload",
    [
        {"method": "kaspi_link", "payment_url": "https://pay.kaspi.kz/pay/evil"},
        {"method": "kaspi_link", "amount_kzt": 1},
        {"method": "cash", "status": "paid"},
        {"method": "card"},
        {},
    ],
)
async def test_forged_method_bodies_are_rejected(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    payload: dict[str, Any],
) -> None:
    response = await pay(client, completed.ride_id, "method", completed.passenger, json=payload)

    expect_error(response, 422, "validation_error")
    await expect_unpaid_cash(session_factory, completed.ride_id)


# Removed commands and CSRF


@pytest.mark.parametrize("action", ["report", "confirm"])
@pytest.mark.parametrize("username", ["pat", "dana", ADMIN])
async def test_report_and_confirm_no_longer_exist(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    action: str,
    username: str,
) -> None:
    response = await pay(client, completed.ride_id, action, username)

    assert response.status_code in (404, 405), response.text
    await expect_unpaid_cash(session_factory, completed.ride_id)


@pytest.mark.parametrize(
    ("method", "action", "payload"), [("put", "method", KASPI), ("post", "pay", None)]
)
async def test_commands_need_the_csrf_token(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    method: str,
    action: str,
    payload: dict[str, Any] | None,
) -> None:
    await login_as(client, completed.passenger)

    response = await client.request(
        method.upper(), payment_url(completed.ride_id, action), json=payload
    )

    expect_error(response, 403, "csrf_failed")
    await expect_unpaid_cash(session_factory, completed.ride_id)
