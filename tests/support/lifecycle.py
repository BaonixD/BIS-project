"""Ride commands through the API and the ``ride_events`` history.

Usage in an API test with the ``client``, ``driver_factory``, ``dispatcher`` and
``session_factory`` fixtures::

    trip = await trip_in("arrived", client, driver_factory, dispatcher)
    response = await send(client, trip.ride_id, "start", trip.driver)
    assert [event.command for event in await ride_events(session_factory, trip.ride_id)] == [
        "assign", "arrive", "start"
    ]

The client keeps one session cookie: ``send`` logs in as the user it acts for.
The passenger is ``pat`` and the driver ``dana`` (next to the default pickup).
"""

import uuid
from dataclasses import dataclass
from typing import Any, Final

import httpx
from sqlalchemy import literal_column, select

from support.auth import register_and_login
from support.dispatch import Dispatcher, accept_url
from support.drivers import DriverFactory, login_as
from support.rides import order_ride, ride_url
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.models import RideEvent

PASSENGER: Final = "pat"
DRIVER: Final = "dana"
NEAR_PICKUP: Final = Coordinates(longitude=76.9580, latitude=43.2389)
DRIVER_COMMANDS: Final = ("arrive", "start", "complete", "release")
RIDE_COMMANDS: Final = (*DRIVER_COMMANDS, "cancel")
RELEASE_BODY: Final = {"reason": "flat tyre"}

# Driver commands that lead from ``assigned`` to each later status.
_PATH: Final = {
    "assigned": (),
    "arrived": ("arrive",),
    "in_progress": ("arrive", "start"),
    "completed": ("arrive", "start", "complete"),
}


def command_url(ride_id: uuid.UUID | str, command: str) -> str:
    return f"{ride_url(ride_id)}/{command}"


@dataclass(frozen=True)
class Trip:
    ride_id: uuid.UUID
    offer_id: uuid.UUID
    driver_id: uuid.UUID
    passenger_id: uuid.UUID
    passenger: str = PASSENGER
    driver: str = DRIVER


@dataclass(frozen=True)
class Event:
    from_status: str
    to_status: str
    command: str
    actor_id: uuid.UUID | None
    reason: str | None


def body_for(command: str) -> dict[str, Any] | None:
    """A valid body: release needs a reason, the other commands need none."""
    return RELEASE_BODY if command == "release" else None


async def send(
    client: httpx.AsyncClient,
    ride_id: uuid.UUID | str,
    command: str,
    username: str,
    *,
    json: dict[str, Any] | None = None,
    csrf: bool = True,
) -> httpx.Response:
    """Log in as ``username`` and POST the command (with a release reason by default)."""
    user = await login_as(client, username)
    payload = json if json is not None else body_for(command)
    return await client.post(
        command_url(ride_id, command), json=payload, headers=user.csrf_headers if csrf else {}
    )


async def searching_trip(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    *,
    payment_method: str | None = None,
) -> Trip:
    """``pat`` ordered a ride; ``dana`` (approved, online, nearby) has its pending offer."""
    driver_id = await driver_factory.driver(DRIVER, location=NEAR_PICKUP)
    passenger = await register_and_login(client, PASSENGER)
    ride = await order_ride(client, passenger, payment_method=payment_method)
    ride_id = uuid.UUID(ride["id"])
    offer = await dispatcher.pending(ride_id)
    assert offer is not None
    assert offer.driver_id == driver_id
    return Trip(ride_id=ride_id, offer_id=offer.id, driver_id=driver_id, passenger_id=passenger.id)


async def accept(client: httpx.AsyncClient, trip: Trip) -> httpx.Response:
    driver = await login_as(client, trip.driver)
    return await client.post(accept_url(trip.offer_id), headers=driver.csrf_headers)


async def trip_in(
    status: str,
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    *,
    payment_method: str | None = None,
) -> Trip:
    """A trip of ``pat`` and ``dana`` brought to ``status`` through the API.

    ``searching``: dana's offer is pending; ``cancelled``: cancelled after dana
    accepted; ``no_driver``: no driver exists, the search ended at once.
    ``payment_method`` is sent with the order (cash when omitted).
    """
    if status == "no_driver":
        passenger = await register_and_login(client, PASSENGER)
        ride = await order_ride(client, passenger, payment_method=payment_method)
        assert ride["status"] == "no_driver"
        missing = uuid.UUID(int=0)
        return Trip(
            ride_id=uuid.UUID(ride["id"]),
            offer_id=missing,
            driver_id=missing,
            passenger_id=passenger.id,
        )
    trip = await searching_trip(client, driver_factory, dispatcher, payment_method=payment_method)
    if status == "searching":
        return trip
    accepted = await accept(client, trip)
    assert accepted.status_code == 200, accepted.text
    if status == "cancelled":
        await expect_ok(client, trip, "cancel")
        return trip
    for command in _PATH[status]:
        await expect_ok(client, trip, command)
    return trip


async def expect_ok(client: httpx.AsyncClient, trip: Trip, command: str) -> dict[str, Any]:
    """Run the command as the user entitled to it; it must answer 200."""
    username = trip.passenger if command == "cancel" else trip.driver
    response = await send(client, trip.ride_id, command, username)
    assert response.status_code == 200, response.text
    ride: dict[str, Any] = response.json()
    return ride


async def ride_events(session_factory: SessionFactory, ride_id: uuid.UUID) -> list[Event]:
    """The ride's history, oldest first.

    The test clock often stands still between commands; SQLite's ``rowid``
    (insertion order) breaks ties of ``created_at`` here, in tests only.
    """
    query = (
        select(RideEvent)
        .where(RideEvent.ride_id == ride_id)
        .order_by(RideEvent.created_at, literal_column("rowid"))
    )
    async with session_factory() as session, read_transaction(session):
        rows = list(await session.scalars(query))
    return [
        Event(
            from_status=row.from_status.value,
            to_status=row.to_status.value,
            command=row.command.value,
            actor_id=row.actor_id,
            reason=row.reason,
        )
        for row in rows
    ]


async def commands_of(session_factory: SessionFactory, ride_id: uuid.UUID) -> list[str]:
    return [event.command for event in await ride_events(session_factory, ride_id)]
