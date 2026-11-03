"""Completing a ride opens its payment once, in the same transaction (ADR 0004, ADR 0007)."""

import asyncio

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import command_url, commands_of, expect_ok, send, trip_in
from support.payments import StoredPayment, stored_payment
from support.rides import count_rows
from support.rows import insert_payment
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.models import Payment


async def test_complete_opens_one_unpaid_cash_payment_with_the_ride_amount(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    ride = await expect_ok(client, trip, "complete")

    assert await stored_payment(session_factory, trip.ride_id) == StoredPayment(
        amount_kzt=ride["amount_kzt"],
        currency="KZT",
        method="cash",
        status="unpaid",
        paid_at=None,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    assert ride["amount_kzt"] == (await dispatcher.ride(trip.ride_id)).amount_kzt == 2200


async def test_repeated_complete_opens_no_second_payment(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)

    await expect_ok(client, trip, "complete")

    assert await count_rows(session_factory, Payment) == 1


@pytest.mark.parametrize("status", ["searching", "assigned", "arrived", "in_progress", "cancelled"])
async def test_a_ride_that_is_not_completed_has_no_payment(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    status: str,
) -> None:
    await trip_in(status, client, driver_factory, dispatcher)

    assert await count_rows(session_factory, Payment) == 0


async def test_failed_payment_opening_rolls_the_completion_back(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    # A conflicting row makes the payment insert of the completion fail in the database.
    await insert_payment(session_factory, trip.ride_id.hex)

    # The app answers 500; the test transport re-raises the unhandled error.
    with pytest.raises(IntegrityError, match="UNIQUE"):
        await send(client, trip.ride_id, "complete", trip.driver)

    ride = await dispatcher.ride(trip.ride_id)
    assert (ride.status.value, ride.completed_at) == ("in_progress", None)
    assert "complete" not in await commands_of(session_factory, trip.ride_id)
    assert await count_rows(session_factory, Payment) == 1


async def test_concurrent_completes_open_one_payment(
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
