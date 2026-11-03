"""Payment chosen before the order (ADR 0010): cash or the Kaspi link.

Kaspi is on with ``TEST_KASPI_URL``; no request leaves the test process and no
real payment is made: the Kaspi charge on accept is only simulated.
Passenger ``pat``, driver ``dana``, admin ``admin``.
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
from support.lifecycle import NEAR_PICKUP, Trip, accept, expect_ok, send, trip_in
from support.payments import (
    ADMIN,
    TEST_KASPI_URL,
    cash_received,
    expect_cash_received,
    kaspi_on,
    payment_url,
    read_payment,
    stored_payment,
)
from support.rows import insert_driver, insert_payment, insert_ride
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.config import PaymentSettings

KASPI = "kaspi_link"


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


@pytest.fixture
async def completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> Trip:
    """A completed cash trip of ``pat`` with ``dana``; the admin account exists."""
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


def at(body: dict[str, Any], field: str) -> datetime:
    return datetime.fromisoformat(body[field])


async def expect_unpaid_cash(session_factory: SessionFactory, ride_id: uuid.UUID) -> None:
    stored = await stored_payment(session_factory, ride_id)
    assert stored is not None
    assert (stored.method, stored.status, stored.paid_at) == ("cash", "unpaid", None)


# Reading


async def test_passenger_sees_an_unpaid_cash_payment_right_after_ordering(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)

    body = await read_payment(client, trip.ride_id, trip.passenger)

    assert body == {
        "ride_id": str(trip.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": "cash",
        "status": "unpaid",
        "paid_at": None,
        "refunded_at": None,
        "payment_url": None,
    }


@pytest.mark.parametrize(
    "status", ["searching", "assigned", "arrived", "in_progress", "completed", "cancelled"]
)
async def test_payment_is_readable_in_every_ride_status(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    body = await read_payment(client, trip.ride_id, trip.passenger)

    assert (body["method"], body["status"]) == ("cash", "unpaid")


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


# Kaspi: charged when a driver accepts, refunded when the ride does not happen after that


async def test_kaspi_order_waits_unpaid_for_a_driver(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher, payment_method=KASPI)

    body = await read_payment(client, trip.ride_id, trip.passenger)

    assert body == {
        "ride_id": str(trip.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": KASPI,
        "status": "unpaid",
        "paid_at": None,
        "refunded_at": None,
        "payment_url": TEST_KASPI_URL,
    }
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert (stored.status, stored.created_at) == ("unpaid", clock.now())


async def test_accept_charges_the_kaspi_payment(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher, payment_method=KASPI)
    clock.advance(timedelta(seconds=10))

    accepted = await accept(client, trip)

    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["status"], accepted.json()["payment_status"]) == ("assigned", "paid")
    body = await read_payment(client, trip.ride_id, trip.passenger)
    assert (body["status"], body["refunded_at"]) == ("paid", None)
    assert at(body, "paid_at") == clock.now()
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert (stored.status, stored.paid_at, stored.updated_at) == ("paid", clock.now(), clock.now())


async def test_repeated_accept_keeps_the_first_charge(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher, payment_method=KASPI)
    first = await read_payment(client, trip.ride_id, trip.passenger)
    clock.advance(timedelta(seconds=5))

    repeated = await accept(client, trip)

    assert repeated.status_code == 200, repeated.text
    assert await read_payment(client, trip.ride_id, trip.passenger) == first


async def test_accept_leaves_a_cash_payment_unpaid(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)

    await expect_unpaid_cash(session_factory, trip.ride_id)


async def test_cancel_before_a_driver_charges_nothing(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher, payment_method=KASPI)

    cancelled = await expect_ok(client, trip, "cancel")

    assert (cancelled["payment_method"], cancelled["payment_status"]) == (KASPI, "unpaid")
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert (stored.status, stored.paid_at, stored.refunded_at) == ("unpaid", None, None)


@pytest.mark.parametrize("status", ["assigned", "arrived"])
async def test_passenger_cancel_refunds_a_kaspi_payment(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher, payment_method=KASPI)
    paid = await read_payment(client, trip.ride_id, trip.passenger)
    clock.advance(timedelta(minutes=1))

    cancelled = await expect_ok(client, trip, "cancel")

    assert (cancelled["payment_method"], cancelled["payment_status"]) == (KASPI, "refunded")
    body = await read_payment(client, trip.ride_id, trip.passenger)
    assert body["status"] == "refunded"
    assert at(body, "refunded_at") == clock.now()
    assert body["paid_at"] == paid["paid_at"]
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert (stored.status, stored.refunded_at, stored.updated_at) == (
        "refunded",
        clock.now(),
        clock.now(),
    )


async def test_repeated_cancel_keeps_the_first_refund(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher, payment_method=KASPI)
    await expect_ok(client, trip, "cancel")
    first = await read_payment(client, trip.ride_id, trip.passenger)
    clock.advance(timedelta(minutes=1))

    await expect_ok(client, trip, "cancel")

    assert await read_payment(client, trip.ride_id, trip.passenger) == first


async def test_no_driver_charges_nothing(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("no_driver", client, driver_factory, dispatcher, payment_method=KASPI)

    body = await read_payment(client, trip.ride_id, trip.passenger)

    assert (body["method"], body["status"]) == (KASPI, "unpaid")
    assert (body["paid_at"], body["refunded_at"]) == (None, None)


async def test_search_running_out_before_a_driver_charges_nothing(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher, payment_method=KASPI)
    clock.advance(timedelta(minutes=10))

    await dispatcher.process(trip.ride_id)

    body = await read_payment(client, trip.ride_id, trip.passenger)
    assert (body["status"], body["paid_at"], body["refunded_at"]) == ("unpaid", None, None)


async def test_release_by_the_driver_keeps_the_kaspi_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher, payment_method=KASPI)
    await driver_factory.driver("next_driver", location=NEAR_PICKUP)
    paid = await read_payment(client, trip.ride_id, trip.passenger)

    released = await expect_ok(client, trip, "release")

    assert (released["status"], released["payment_status"]) == ("searching", "paid")
    assert await read_payment(client, trip.ride_id, trip.passenger) == paid


async def test_next_driver_keeps_the_charge_made_for_the_first(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher, payment_method=KASPI)
    next_driver = await driver_factory.driver("next_driver", location=NEAR_PICKUP)
    paid = await read_payment(client, trip.ride_id, trip.passenger)
    await expect_ok(client, trip, "release")
    offer = await dispatcher.pending(trip.ride_id)
    assert offer is not None
    clock.advance(timedelta(seconds=10))

    ride = await dispatcher.accept(offer.id, next_driver)

    assert ride.driver_id == next_driver
    assert await read_payment(client, trip.ride_id, trip.passenger) == paid


async def test_search_running_out_after_release_refunds_the_charge(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher, payment_method=KASPI)
    paid = await read_payment(client, trip.ride_id, trip.passenger)
    clock.advance(timedelta(minutes=1))

    released = await expect_ok(client, trip, "release")  # no other driver: no_driver at once

    assert (released["status"], released["payment_status"]) == ("no_driver", "refunded")
    body = await read_payment(client, trip.ride_id, trip.passenger)
    assert body["paid_at"] == paid["paid_at"]
    assert at(body, "refunded_at") == clock.now()


@pytest.mark.parametrize("status", ["cancelled", "no_driver"])
async def test_an_unpaid_cash_payment_is_not_refunded(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    status: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    await expect_unpaid_cash(session_factory, trip.ride_id)


async def test_completed_kaspi_ride_stays_paid(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher, payment_method=KASPI)

    body = await read_payment(client, trip.ride_id, trip.passenger)

    assert (body["method"], body["status"], body["refunded_at"]) == (KASPI, "paid", None)


# Cash: the assigned driver confirms the money after completion


async def test_driver_receives_cash_after_completion(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    body = await expect_cash_received(client, completed.ride_id, completed.driver)

    assert body == {
        "ride_id": str(completed.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": "cash",
        "status": "paid",
        "paid_at": body["paid_at"],
        "refunded_at": None,
        "payment_url": None,
    }
    assert at(body, "paid_at") == clock.now()
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.status, stored.paid_at, stored.updated_at) == ("paid", clock.now(), clock.now())
    for username in (completed.passenger, ADMIN):
        assert (await read_payment(client, completed.ride_id, username))["status"] == "paid"


async def test_repeated_cash_received_answers_the_same_payment(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    first = await expect_cash_received(client, completed.ride_id, completed.driver)
    clock.advance(timedelta(minutes=5))

    again = await expect_cash_received(client, completed.ride_id, completed.driver)

    assert again == first
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.paid_at == stored.updated_at == at(first, "paid_at")


@pytest.mark.parametrize("username", ["pat", ADMIN])
async def test_only_the_assigned_driver_receives_cash(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory, username: str
) -> None:
    response = await cash_received(client, completed.ride_id, username)

    body = expect_error(response, 403, "payment_action_forbidden")
    assert body["error"]["details"] == {"action": "cash_received"}
    await expect_unpaid_cash(session_factory, completed.ride_id)


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_receive_cash(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    session_factory: SessionFactory,
    role: str,
) -> None:
    username = await stranger(client, driver_factory, role)

    expect_error(await cash_received(client, completed.ride_id, username), 404, "ride_not_found")
    await expect_unpaid_cash(session_factory, completed.ride_id)


async def test_cash_received_for_an_unknown_ride(
    client: httpx.AsyncClient, completed: Trip
) -> None:
    response = await cash_received(client, uuid.uuid4(), completed.driver)

    expect_error(response, 404, "ride_not_found")


@pytest.mark.parametrize("status", ["assigned", "in_progress", "cancelled"])
async def test_cash_is_received_only_after_completion(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    status: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    response = await cash_received(client, trip.ride_id, trip.driver)

    expect_error(response, 409, "ride_not_completed")
    await expect_unpaid_cash(session_factory, trip.ride_id)


async def test_cash_received_is_not_for_a_kaspi_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher, payment_method=KASPI)
    before = await read_payment(client, trip.ride_id, trip.passenger)

    response = await cash_received(client, trip.ride_id, trip.driver)

    body = expect_error(response, 409, "invalid_payment_transition")
    assert body["error"]["details"] == {"action": "cash_received", "status": "paid"}
    assert await read_payment(client, trip.ride_id, trip.passenger) == before


async def test_a_body_cannot_change_what_is_received(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    response = await cash_received(
        client, completed.ride_id, completed.driver, json={"amount_kzt": 1, "method": KASPI}
    )

    assert response.status_code == 200, response.text
    assert (response.json()["amount_kzt"], response.json()["method"]) == (2200, "cash")
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.amount_kzt, stored.method, stored.status) == (2200, "cash", "paid")


async def test_concurrent_cash_received_record_one_payment(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    first = await login_as(client, completed.driver)
    second = await login_as(other_client, completed.driver)
    url = payment_url(completed.ride_id, "cash-received")

    responses = await asyncio.gather(
        client.post(url, headers=first.csrf_headers),
        other_client.post(url, headers=second.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.status == "paid"


async def test_receiving_cash_of_one_ride_leaves_other_rides_alone(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    other_ride = await insert_ride(
        session_factory, status="completed", driver_id=await insert_driver(session_factory)
    )
    await insert_payment(session_factory, other_ride)

    await expect_cash_received(client, completed.ride_id, completed.driver)

    await expect_unpaid_cash(session_factory, uuid.UUID(other_ride))


async def test_cash_received_needs_the_csrf_token(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await login_as(client, completed.driver)

    response = await client.post(payment_url(completed.ride_id, "cash-received"))

    expect_error(response, 403, "csrf_failed")
    await expect_unpaid_cash(session_factory, completed.ride_id)


# Removed commands


@pytest.mark.parametrize(
    ("method", "action"),
    [("put", "method"), ("post", "pay"), ("post", "report"), ("post", "confirm")],
)
@pytest.mark.parametrize("username", ["pat", "dana", ADMIN])
async def test_old_payment_commands_no_longer_exist(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    method: str,
    action: str,
    username: str,
) -> None:
    user = await login_as(client, username)

    response = await client.request(
        method.upper(),
        payment_url(completed.ride_id, action),
        json={"method": KASPI},
        headers=user.csrf_headers,
    )

    assert response.status_code in (404, 405), response.text
    await expect_unpaid_cash(session_factory, completed.ride_id)


async def test_cancel_of_a_cash_ride_after_release_changes_nothing(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    await driver_factory.driver("next_driver", location=NEAR_PICKUP)
    await expect_ok(client, trip, "release")

    response = await send(client, trip.ride_id, "cancel", trip.passenger)

    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "unpaid"
    await expect_unpaid_cash(session_factory, trip.ride_id)
