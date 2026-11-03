"""The order opens the ride's payment in its own transaction; later commands keep it (ADR 0010).

Kaspi is on with ``TEST_KASPI_URL``; a Kaspi order is only a simulated charge.
"""

import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import NEAR_PICKUP, command_url, commands_of, expect_ok, send, trip_in
from support.payments import StoredPayment, kaspi_on, stored_payment
from support.rides import RIDES_URL, count_rows, request_quote, ride_body, ride_headers
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.models import Payment
from taxi_service.modules.rides.models import IdempotencyRecord, Ride

RECORDS = "taxi_service.modules.payments.records"


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


@pytest.mark.parametrize("method", [None, "cash"])
async def test_order_opens_one_unpaid_cash_payment_with_the_ride_amount(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
    method: str | None,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher, payment_method=method)

    assert await stored_payment(session_factory, trip.ride_id) == StoredPayment(
        amount_kzt=(await dispatcher.ride(trip.ride_id)).amount_kzt,
        currency="KZT",
        method="cash",
        status="unpaid",
        paid_at=None,
        refunded_at=None,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    assert await count_rows(session_factory, Payment) == 1


@pytest.mark.parametrize(
    ("method", "status"), [(None, "unpaid"), ("cash", "unpaid"), ("kaspi_link", "paid")]
)
async def test_ride_responses_carry_the_payment(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    method: str | None,
    status: str,
) -> None:
    await driver_factory.driver("dana", location=NEAR_PICKUP)
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    created = await client.post(
        RIDES_URL, json=ride_body(quote["quote_id"], method), headers=ride_headers(passenger)
    )

    assert created.status_code == 201, created.text
    expected = (method or "cash", status)
    assert (created.json()["payment_method"], created.json()["payment_status"]) == expected
    shown = (await client.get(f"{RIDES_URL}/{created.json()['id']}")).json()
    assert (shown["payment_method"], shown["payment_status"]) == expected


async def test_command_responses_carry_the_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    completed = await expect_ok(client, trip, "complete")

    assert (completed["payment_method"], completed["payment_status"]) == ("cash", "unpaid")


async def test_complete_opens_no_second_payment_and_keeps_the_first(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    before = await stored_payment(session_factory, trip.ride_id)

    await expect_ok(client, trip, "complete")
    await expect_ok(client, trip, "complete")

    assert await stored_payment(session_factory, trip.ride_id) == before
    assert await count_rows(session_factory, Payment) == 1


async def test_failed_payment_opening_rolls_the_order_back(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing(*args: Any, **kwargs: Any) -> Payment:
        raise RuntimeError("payment record failed")

    monkeypatch.setattr(RECORDS + ".open_payment", failing)
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    # The app answers 500; the test transport re-raises the unhandled error.
    with pytest.raises(RuntimeError, match="payment record failed"):
        await client.post(
            RIDES_URL, json=ride_body(quote["quote_id"]), headers=ride_headers(passenger)
        )

    for model in (Ride, Payment, IdempotencyRecord):
        assert await count_rows(session_factory, model) == 0


async def test_failed_refund_rolls_the_cancel_back(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip = await trip_in(
        "assigned", client, driver_factory, dispatcher, payment_method="kaspi_link"
    )

    async def failing(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("refund failed")

    monkeypatch.setattr(RECORDS + ".refund_if_paid", failing)

    with pytest.raises(RuntimeError, match="refund failed"):
        await send(client, trip.ride_id, "cancel", trip.passenger)

    assert (await dispatcher.ride(trip.ride_id)).status.value == "assigned"
    assert "cancel" not in await commands_of(session_factory, trip.ride_id)
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert stored.status == "paid"


async def test_concurrent_completes_keep_one_payment(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    first = await login_as(client, trip.driver)
    second = await login_as(other_client, trip.driver)

    responses = await asyncio.gather(
        client.post(command_url(trip.ride_id, "complete"), headers=first.csrf_headers),
        other_client.post(command_url(trip.ride_id, "complete"), headers=second.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert await count_rows(session_factory, Payment) == 1


async def test_concurrent_cancels_refund_once(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in(
        "assigned", client, driver_factory, dispatcher, payment_method="kaspi_link"
    )
    first = await login_as(client, trip.passenger)
    second = await login_as(other_client, trip.passenger)

    responses = await asyncio.gather(
        client.post(command_url(trip.ride_id, "cancel"), headers=first.csrf_headers),
        other_client.post(command_url(trip.ride_id, "cancel"), headers=second.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    async with session_factory() as session, read_transaction(session):
        [payment] = list(await session.scalars(select(Payment)))
    assert payment.status.value == "refunded"
    assert (await commands_of(session_factory, trip.ride_id)).count("cancel") == 1
