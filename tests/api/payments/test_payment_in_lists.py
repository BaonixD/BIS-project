"""Ride history and the admin ride list show each ride's payment status and method (T09 + T08).

Both are null until the ride is completed; one JOIN keeps a page at the same
number of SQL statements whatever its size.
"""

import uuid
from typing import Any

import httpx
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
from support.payments import ADMIN, expect_paid_ok
from support.rides import RIDES_URL, RideFactory
from support.rows import insert_payment
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
    await expect_paid_ok(client, trip.ride_id, "pay", trip.passenger)
    [paid] = (await get_page(client, RIDES_URL))["items"]

    assert payment_of(unpaid) == ("unpaid", "cash")
    assert payment_of(paid) == ("paid", "cash")


async def test_rides_without_payment_show_null(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    await login_as(client, trip.driver)

    [item] = (await get_page(client, RIDES_URL))["items"]

    assert item["status"] == "in_progress"
    assert payment_of(item) == (None, None)


async def test_admin_list_shows_the_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    await driver_factory.admin_id()
    await expect_paid_ok(client, trip.ride_id, "pay", trip.passenger)
    await login_as(client, ADMIN)

    [item] = (await get_page(client, ADMIN_RIDES_URL))["items"]

    assert item["id"] == str(trip.ride_id)
    assert payment_of(item) == ("paid", "cash")


async def seed_paid_rides(
    ride_factory: RideFactory, passenger_id: uuid.UUID, driver_id: uuid.UUID, count: int
) -> None:
    ids = await past_rides(
        ride_factory, passenger_id, count, status=RideStatus.COMPLETED, driver_id=driver_id
    )
    for ride_id in ids:
        await insert_payment(ride_factory.session_factory, ride_id.hex)


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
