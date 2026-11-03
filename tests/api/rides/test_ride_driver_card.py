"""GET /rides/{id} shows the driver to the participants of an active ride (MVP_SPEC §6).

While the ride is assigned, arrived or in_progress its passenger and its
driver see the driver's name, phone, car and last location with the server
time of that location; nobody else does, and no location history is kept. A
location that stopped updating is shown as it is: it never ends the ride.
After completion the participants still see the card for the receipt, but
without any location (ADR 0007).
"""

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest

from support.auth import register_and_login
from support.clock import DEFAULT_START, ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import NEAR_PICKUP, send, trip_in
from support.rides import ride_url
from taxi_service.modules.geo.schemas import Coordinates

ACTIVE = ("assigned", "arrived", "in_progress")
MOVED = Coordinates(longitude=76.9575, latitude=43.2391)


def card(
    location: Coordinates | None = NEAR_PICKUP, at: datetime | None = DEFAULT_START
) -> dict[str, Any]:
    """Dana's card as ``support.drivers.complete_profile`` and ``DriverFactory`` made her."""
    return {
        "full_name": "Dana Driver",
        "phone": "+77011234567",
        "vehicle": {
            "make": "Toyota",
            "model": "Camry",
            "color": "white",
            "plate_number": "001TST02",
            "car_class": "economy",
        },
        "location": None if location is None else location.model_dump(),
        "location_updated_at": None if at is None else at.isoformat().replace("+00:00", "Z"),
        "rating": {"average": None, "count": 0},
    }


async def read_as(client: httpx.AsyncClient, ride_id: object, username: str) -> dict[str, Any]:
    await login_as(client, username)
    response = await client.get(ride_url(str(ride_id)))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def same_card(shown: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    if shown is None:
        return False
    return {**shown, "location_updated_at": _moment(shown["location_updated_at"])} == {
        **expected,
        "location_updated_at": _moment(expected["location_updated_at"]),
    }


def _moment(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


@pytest.mark.parametrize("status", ACTIVE)
async def test_participants_see_the_driver_of_an_active_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    for username in (trip.passenger, trip.driver):
        ride = await read_as(client, trip.ride_id, username)
        assert ride["status"] == status
        assert same_card(ride["driver"], card()), ride["driver"]


async def test_participants_see_the_driver_of_a_completed_ride_without_location(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    clock.advance(timedelta(seconds=20))
    await driver_factory.move(trip.driver_id, MOVED)

    for username in (trip.passenger, trip.driver):
        ride = await read_as(client, trip.ride_id, username)
        assert ride["status"] == "completed"
        assert same_card(ride["driver"], card(location=None, at=None)), ride["driver"]


@pytest.mark.parametrize("status", ["searching", "cancelled", "no_driver"])
async def test_no_driver_card_outside_an_active_or_completed_ride(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    ride = await read_as(client, trip.ride_id, trip.passenger)

    assert ride["status"] == status
    assert ride["driver"] is None


@pytest.mark.parametrize("status", ["assigned", "completed"])
async def test_admin_reads_the_ride_without_the_driver_card(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    ride = await read_as(client, trip.ride_id, "admin")

    assert ride["status"] == status
    assert ride["driver"] is None


@pytest.mark.parametrize("status", ["assigned", "completed"])
async def test_other_users_see_neither_the_ride_nor_the_driver(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    await driver_factory.driver("other_driver", location=MOVED)
    await register_and_login(client, "other_passenger")

    for username in ("other_passenger", "other_driver"):
        await login_as(client, username)
        response = await client.get(ride_url(trip.ride_id))
        assert response.status_code == 404
        assert "Dana" not in response.text


async def test_card_follows_the_last_location_without_a_history(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    clock.advance(timedelta(seconds=20))
    await driver_factory.move(trip.driver_id, MOVED)

    ride = await read_as(client, trip.ride_id, trip.passenger)

    assert same_card(ride["driver"], card(MOVED, clock.now())), ride["driver"]


async def test_stale_location_neither_ends_nor_cancels_the_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    trip = await trip_in("arrived", client, driver_factory, dispatcher)

    clock.advance(timedelta(minutes=15))
    await dispatcher.process_due()
    await dispatcher.process_due()

    ride = await read_as(client, trip.ride_id, trip.passenger)
    assert ride["status"] == "arrived"
    assert same_card(ride["driver"], card()), ride["driver"]
    started = await send(client, trip.ride_id, "start", trip.driver)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"
