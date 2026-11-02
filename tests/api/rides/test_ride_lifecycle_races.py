"""Two requests at the same time on one ride: exactly one outcome, status and history agree.

Each user has its own client (cookies), the requests run concurrently with
``asyncio.gather`` against one application and one SQLite file. SQLite
serializes the write transactions (``BEGIN IMMEDIATE``); these tests show that
whichever request goes first, the second sees its result.
"""

import asyncio
from datetime import datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from support.dispatch import Dispatcher, accept_url
from support.drivers import DriverFactory, login_as
from support.lifecycle import command_url, commands_of, ride_events, trip_in
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import OfferStatus


async def test_accept_against_cancel(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    driver = await login_as(client, trip.driver)
    passenger = await login_as(other_client, trip.passenger)

    accepted, cancelled = await asyncio.gather(
        client.post(accept_url(trip.offer_id), headers=driver.csrf_headers),
        other_client.post(command_url(trip.ride_id, "cancel"), headers=passenger.csrf_headers),
    )

    assert cancelled.status_code == 200, cancelled.text
    ride = await dispatcher.ride(trip.ride_id)
    [offer] = await dispatcher.offers(trip.ride_id)
    assert ride.status.value == "cancelled"
    if accepted.status_code == 200:
        assert await commands_of(session_factory, trip.ride_id) == ["assign", "cancel"]
        assert (ride.driver_id, offer.status) == (trip.driver_id, OfferStatus.ACCEPTED)
    else:
        assert accepted.status_code == 409
        assert accepted.json()["error"]["code"] == "invalid_ride_transition"
        assert await commands_of(session_factory, trip.ride_id) == ["cancel"]
        assert (ride.driver_id, offer.status) == (None, OfferStatus.REVOKED)


async def test_start_against_cancel(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("arrived", client, driver_factory, dispatcher)
    driver = await login_as(client, trip.driver)
    passenger = await login_as(other_client, trip.passenger)

    started, cancelled = await asyncio.gather(
        client.post(command_url(trip.ride_id, "start"), headers=driver.csrf_headers),
        other_client.post(command_url(trip.ride_id, "cancel"), headers=passenger.csrf_headers),
    )

    codes = sorted([started.status_code, cancelled.status_code])
    assert codes == [200, 409]
    winner = "start" if started.status_code == 200 else "cancel"
    expected = {"start": "in_progress", "cancel": "cancelled"}[winner]
    assert (await dispatcher.ride(trip.ride_id)).status.value == expected
    assert await commands_of(session_factory, trip.ride_id) == ["assign", "arrive", winner]


class CountingHook:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, session: AsyncSession, ride: Ride, now: datetime) -> None:
        self.calls += 1


@pytest.fixture
def completion(app: FastAPI) -> CountingHook:
    hook = CountingHook()
    app.state.ride_completion_hook = hook
    return hook


async def test_complete_against_complete(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    completion: CountingHook,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    first = await login_as(client, trip.driver)
    second = await login_as(other_client, trip.driver)

    responses = await asyncio.gather(
        client.post(command_url(trip.ride_id, "complete"), headers=first.csrf_headers),
        other_client.post(command_url(trip.ride_id, "complete"), headers=second.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert {response.json()["status"] for response in responses} == {"completed"}
    assert completion.calls == 1
    assert (await commands_of(session_factory, trip.ride_id)).count("complete") == 1


async def test_release_against_cancel(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    driver = await login_as(client, trip.driver)
    passenger = await login_as(other_client, trip.passenger)

    released, cancelled = await asyncio.gather(
        client.post(
            command_url(trip.ride_id, "release"),
            json={"reason": "flat tyre"},
            headers=driver.csrf_headers,
        ),
        other_client.post(command_url(trip.ride_id, "cancel"), headers=passenger.csrf_headers),
    )

    ride = await dispatcher.ride(trip.ride_id)
    events = await ride_events(session_factory, trip.ride_id)
    history = [event.command for event in events]
    codes = (released.status_code, cancelled.status_code)
    # cancel first; release, cancel, then the search step; release and its step, then cancel.
    outcomes = {
        (409, 200): ["assign", "cancel"],
        (200, 200): ["assign", "release", "cancel"],
        (200, 409): ["assign", "release", "mark_no_driver"],
    }
    assert history == outcomes[codes]
    assert ride.status.value == events[-1].to_status
    assert await dispatcher.pending(trip.ride_id) is None
