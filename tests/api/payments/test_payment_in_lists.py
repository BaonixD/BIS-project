"""Ride history and the admin ride list show each ride's payment status and method.

The payment exists from the order on (ADR 0010); one JOIN keeps a page at the
same number of SQL statements whatever its size.
"""

import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.history import (
    ADMIN_RIDES_URL,
    StatementCounter,
    count_statements,
    get_page,
    past_rides,
)
from support.lifecycle import trip_in
from support.payments import ADMIN, expect_cash_received, kaspi_on
from support.rides import RIDES_URL, RideFactory
from taxi_service.modules.rides.states import RideStatus

MAX_QUERIES = 3  # authentication, the page with its payments, the total


def payment_of(item: dict[str, Any]) -> tuple[str | None, str | None]:
    return item["payment_status"], item["payment_method"]


async def test_history_shows_the_payment_of_a_completed_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)

    await login_as(client, trip.passenger)
    [unpaid] = (await get_page(client, RIDES_URL))["items"]
    await expect_cash_received(client, trip.ride_id, trip.driver)
    await login_as(client, trip.passenger)
    [paid] = (await get_page(client, RIDES_URL))["items"]

    assert payment_of(unpaid) == ("unpaid", "cash")
    assert payment_of(paid) == ("paid", "cash")


@pytest.mark.parametrize(
    ("status", "method", "expected"),
    [
        ("in_progress", None, ("unpaid", "cash")),
        ("searching", "kaspi_link", ("unpaid", "kaspi_link")),
        ("assigned", "kaspi_link", ("paid", "kaspi_link")),
        ("cancelled", "kaspi_link", ("refunded", "kaspi_link")),
    ],
)
async def test_unfinished_rides_show_their_payment(
    app: FastAPI,
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    status: str,
    method: str | None,
    expected: tuple[str, str],
) -> None:
    app.state.payment_settings = kaspi_on()
    trip = await trip_in(status, client, driver_factory, dispatcher, payment_method=method)
    await login_as(client, trip.passenger)

    [item] = (await get_page(client, RIDES_URL))["items"]

    assert item["status"] == status
    assert payment_of(item) == expected


async def test_admin_list_shows_the_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    await driver_factory.admin_id()
    await expect_cash_received(client, trip.ride_id, trip.driver)
    await login_as(client, ADMIN)

    [item] = (await get_page(client, ADMIN_RIDES_URL))["items"]

    assert item["id"] == str(trip.ride_id)
    assert payment_of(item) == ("paid", "cash")


async def seed_paid_rides(
    ride_factory: RideFactory, passenger_id: uuid.UUID, driver_id: uuid.UUID, count: int
) -> None:
    """Completed rides with the cash payment their order opened."""
    await past_rides(
        ride_factory, passenger_id, count, status=RideStatus.COMPLETED, driver_id=driver_id
    )


async def page_statements(
    app: FastAPI, client: httpx.AsyncClient, url: str, rides: int
) -> StatementCounter:
    """One page of all ``rides``; the payment join neither duplicates rows nor changes total."""
    with count_statements(app.state.engine) as counter:
        body = await get_page(client, url, limit=100)
    assert (len(body["items"]), body["total"]) == (rides, rides)
    assert len({item["id"] for item in body["items"]}) == rides
    assert {payment_of(item) for item in body["items"]} == {("unpaid", "cash")}
    return counter


async def test_lists_with_payments_cost_the_same_statements_for_10_and_30_rides(
    app: FastAPI,
    client: httpx.AsyncClient,
    ride_factory: RideFactory,
    driver_factory: DriverFactory,
) -> None:
    dana = await driver_factory.driver("dana")
    pat = await ride_factory.passenger("pat")

    await seed_paid_rides(ride_factory, pat, dana, 10)
    await login_as(client, "pat")
    small = await page_statements(app, client, RIDES_URL, 10)
    await login_as(client, ADMIN)
    small_admin = await page_statements(app, client, ADMIN_RIDES_URL, 10)
    await seed_paid_rides(ride_factory, pat, dana, 20)
    await login_as(client, "pat")
    large = await page_statements(app, client, RIDES_URL, 30)
    await login_as(client, ADMIN)
    large_admin = await page_statements(app, client, ADMIN_RIDES_URL, 30)

    assert len(small) == len(large)
    assert len(small_admin) == len(large_admin)
    assert large.queries <= MAX_QUERIES
    assert large_admin.queries <= MAX_QUERIES
