"""Ride commands through the API (MVP_SPEC §6, §8): arrive, start, complete, cancel, release.

The assigned driver moves the ride assigned -> arrived -> in_progress ->
completed or gives it up (release); the passenger cancels before the trip
starts. Every status change, including the system ones of dispatch, is a row
of ``ride_events`` written in the same transaction.
"""

import itertools
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import (
    DRIVER_COMMANDS,
    RIDE_COMMANDS,
    Event,
    Trip,
    accept,
    commands_of,
    expect_ok,
    ride_events,
    searching_trip,
    send,
    trip_in,
)
from support.rides import order_ride, ride_url
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides import dispatch, lifecycle
from taxi_service.modules.rides.models import Ride, RideEvent
from taxi_service.modules.rides.states import OfferStatus, RideCommand, RideStatus
from taxi_service.modules.users.models import UserRole

STEP = timedelta(seconds=5)
OTHER_SPOT = Coordinates(longitude=76.9590, latitude=43.2389)
LIFECYCLE_STATUSES = ("assigned", "arrived", "in_progress", "completed", "cancelled")
ALLOWED = {
    ("assigned", "arrive"): "arrived",
    ("assigned", "cancel"): "cancelled",
    ("arrived", "start"): "in_progress",
    ("arrived", "cancel"): "cancelled",
    ("in_progress", "complete"): "completed",
}
RELEASABLE = ("assigned", "arrived")
REPEATS = {
    ("arrived", "arrive"),
    ("in_progress", "start"),
    ("completed", "complete"),
    ("cancelled", "cancel"),
}
FORBIDDEN = sorted(
    {
        (status, command)
        for status, command in itertools.product(LIFECYCLE_STATUSES, RIDE_COMMANDS)
        if (status, command) not in ALLOWED
        and (status, command) not in REPEATS
        and not (status in RELEASABLE and command == "release")
    }
    | {("no_driver", "cancel")}
)


def error_of(response: httpx.Response) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return error


def actor_of(trip: Trip, command: str) -> str:
    return trip.passenger if command == "cancel" else trip.driver


async def read_ride(client: httpx.AsyncClient, ride_id: uuid.UUID, username: str) -> httpx.Response:
    await login_as(client, username)
    return await client.get(ride_url(ride_id))


def at(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


# The whole trip


async def test_a_ride_goes_from_search_to_completion_through_the_api(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await searching_trip(client, driver_factory, dispatcher)
    times = {}
    clock.advance(STEP)
    times["assigned_at"] = clock.now()
    accepted = await accept(client, trip)
    assert accepted.status_code == 200, accepted.text
    for command, field, status in (
        ("arrive", "arrived_at", "arrived"),
        ("start", "started_at", "in_progress"),
        ("complete", "completed_at", "completed"),
    ):
        clock.advance(STEP)
        times[field] = clock.now()
        response = await send(client, trip.ride_id, command, trip.driver)
        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["id"]) == (status, str(trip.ride_id))

    ride = (await read_ride(client, trip.ride_id, trip.passenger)).json()
    assert ride["status"] == "completed"
    assert ride["driver_id"] == str(trip.driver_id)
    assert {field: at(ride[field]) for field in times} == times
    assert (ride["cancelled_at"], ride["cancel_reason"]) == (None, None)
    assert await ride_events(session_factory, trip.ride_id) == [
        Event("searching", "assigned", "assign", trip.driver_id, None),
        Event("assigned", "arrived", "arrive", trip.driver_id, None),
        Event("arrived", "in_progress", "start", trip.driver_id, None),
        Event("in_progress", "completed", "complete", trip.driver_id, None),
    ]


@pytest.mark.parametrize(("status", "command"), sorted(ALLOWED))
async def test_allowed_command_moves_the_ride_and_records_it(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    status: str,
    command: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    before = await ride_events(session_factory, trip.ride_id)

    response = await send(client, trip.ride_id, command, actor_of(trip, command))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == ALLOWED[(status, command)]
    actor = trip.passenger_id if command == "cancel" else trip.driver_id
    assert await ride_events(session_factory, trip.ride_id) == [
        *before,
        Event(status, ALLOWED[(status, command)], command, actor, None),
    ]


@pytest.mark.parametrize(("status", "command"), FORBIDDEN)
async def test_command_outside_the_state_table_is_409_and_changes_nothing(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    status: str,
    command: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    before = await ride_events(session_factory, trip.ride_id)

    response = await send(client, trip.ride_id, command, actor_of(trip, command))

    assert response.status_code == 409, response.text
    assert error_of(response) == {
        "code": "invalid_ride_transition",
        "message": "The ride command is not allowed in the current ride status.",
        "details": {"current_status": status, "command": command},
    }
    assert await ride_events(session_factory, trip.ride_id) == before
    assert (await dispatcher.ride(trip.ride_id)).status.value == status


@pytest.mark.parametrize(("status", "command"), sorted(REPEATS))
async def test_repeated_command_returns_the_ride_without_a_second_effect(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
    command: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    before = await ride_events(session_factory, trip.ride_id)
    stored = await dispatcher.ride(trip.ride_id)
    clock.advance(STEP)

    response = await send(client, trip.ride_id, command, actor_of(trip, command))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    assert at(response.json()["updated_at"]) == stored.updated_at
    assert await ride_events(session_factory, trip.ride_id) == before


async def test_completed_ride_does_not_come_back(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    before = await ride_events(session_factory, trip.ride_id)

    clock.advance(timedelta(minutes=10))
    await dispatcher.process_due()
    again = await accept(client, trip)

    assert again.status_code == 200
    assert again.json()["status"] == "completed"
    assert (await dispatcher.ride(trip.ride_id)).status.value == "completed"
    assert await ride_events(session_factory, trip.ride_id) == before


# Who may send a command


@pytest.mark.parametrize("command", RIDE_COMMANDS)
async def test_other_users_do_not_see_the_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    command: str,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    await driver_factory.driver("other_driver", location=OTHER_SPOT)
    await register_and_login(client, "other_passenger")
    before = await ride_events(session_factory, trip.ride_id)

    for username in ("other_driver", "other_passenger"):
        response = await send(client, trip.ride_id, command, username)
        assert response.status_code == 404, response.text
        assert error_of(response) == {
            "code": "ride_not_found",
            "message": "Ride not found.",
            "details": {},
        }
    assert await ride_events(session_factory, trip.ride_id) == before


@pytest.mark.parametrize("command", RIDE_COMMANDS)
async def test_unknown_ride_is_404(
    client: httpx.AsyncClient, driver_factory: DriverFactory, command: str
) -> None:
    await driver_factory.driver("dana")
    await register_and_login(client, "pat")

    for username in ("dana", "pat"):
        response = await send(client, uuid.uuid4(), command, username)
        assert response.status_code == 404, response.text
        assert error_of(response)["code"] == "ride_not_found"


@pytest.mark.parametrize("command", DRIVER_COMMANDS)
async def test_driver_of_an_unassigned_ride_is_a_stranger(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, command: str
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)

    response = await send(client, trip.ride_id, command, trip.driver)

    assert response.status_code == 404, response.text
    assert error_of(response)["code"] == "ride_not_found"


@pytest.mark.parametrize(
    ("command", "username"),
    [
        *((command, "pat") for command in DRIVER_COMMANDS),
        ("cancel", "dana"),
        *((command, "admin") for command in RIDE_COMMANDS),
    ],
)
async def test_participant_or_admin_without_the_right_gets_403(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    command: str,
    username: str,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    await driver_factory.admin_id()  # the "admin" account approved dana already
    before = await ride_events(session_factory, trip.ride_id)

    response = await send(client, trip.ride_id, command, username)

    assert response.status_code == 403, response.text
    assert error_of(response) == {
        "code": "ride_command_forbidden",
        "message": "This ride command is not allowed for the current user.",
        "details": {"command": command},
    }
    assert await ride_events(session_factory, trip.ride_id) == before
    assert (await dispatcher.ride(trip.ride_id)).status.value == "assigned"


@pytest.mark.parametrize("command", RIDE_COMMANDS)
async def test_commands_need_the_csrf_token(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, command: str
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)

    response = await send(client, trip.ride_id, command, actor_of(trip, command), csrf=False)

    assert response.status_code == 403
    assert error_of(response)["code"] == "csrf_failed"


@pytest.mark.parametrize("command", RIDE_COMMANDS)
async def test_commands_need_a_session(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, command: str
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    client.cookies.clear()

    response = await client.post(f"{ride_url(trip.ride_id)}/{command}", json=None)

    assert response.status_code == 401
    assert error_of(response)["code"] == "not_authenticated"


# Cancel


async def test_cancel_while_searching_revokes_the_offer_and_ends_the_search(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    await driver_factory.driver("second", location=OTHER_SPOT)
    clock.advance(STEP)

    response = await send(
        client, trip.ride_id, "cancel", trip.passenger, json={"reason": "  plans changed "}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["driver_id"], body["cancel_reason"]) == (
        "cancelled",
        None,
        "plans changed",
    )
    assert at(body["cancelled_at"]) == clock.now()
    [offer] = await dispatcher.offers(trip.ride_id)
    assert (offer.status, offer.responded_at) == (OfferStatus.REVOKED, clock.now())
    clock.advance(timedelta(seconds=40))
    await dispatcher.process_due()
    assert len(await dispatcher.offers(trip.ride_id)) == 1
    assert await ride_events(session_factory, trip.ride_id) == [
        Event("searching", "cancelled", "cancel", trip.passenger_id, "plans changed")
    ]


async def test_cancel_without_a_body_has_no_reason(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    passenger = await login_as(client, trip.passenger)

    response = await client.post(f"{ride_url(trip.ride_id)}/cancel", headers=passenger.csrf_headers)

    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["cancel_reason"]) == ("cancelled", None)


@pytest.mark.parametrize("status", ["assigned", "arrived"])
async def test_cancel_after_assignment_frees_the_driver_for_another_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    status: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)

    cancelled = await expect_ok(client, trip, "cancel")

    assert (cancelled["status"], cancelled["driver_id"]) == ("cancelled", str(trip.driver_id))
    second = await register_and_login(client, "second_passenger")
    ride = await order_ride(client, second)
    offer = await dispatcher.pending(uuid.UUID(ride["id"]))
    assert offer is not None
    assert offer.driver_id == trip.driver_id
    driver = await login_as(client, trip.driver)
    accepted = await client.post(
        f"/api/v1/ride-offers/{offer.id}/accept", headers=driver.csrf_headers
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "assigned"


@pytest.mark.parametrize(
    "reason", ["", "   ", "x" * 201, "line\nbreak", "bell\x07", "nul\x00", "del\x7f"]
)
async def test_cancel_reason_is_short_plain_text(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, reason: str
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)

    response = await send(client, trip.ride_id, "cancel", trip.passenger, json={"reason": reason})

    assert response.status_code == 422, response.text
    assert error_of(response)["code"] == "validation_error"
    assert (await dispatcher.ride(trip.ride_id)).status.value == "searching"


async def test_cancel_reason_may_have_200_characters(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)

    response = await send(
        client, trip.ride_id, "cancel", trip.passenger, json={"reason": "я" * 200}
    )

    assert response.status_code == 200, response.text
    assert response.json()["cancel_reason"] == "я" * 200


# Accepting after a cancellation


async def test_accepting_again_after_the_passenger_cancelled_is_409(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("cancelled", client, driver_factory, dispatcher)
    before = await ride_events(session_factory, trip.ride_id)

    response = await accept(client, trip)

    assert response.status_code == 409, response.text
    assert error_of(response) == {
        "code": "invalid_ride_transition",
        "message": "The ride command is not allowed in the current ride status.",
        "details": {"current_status": "cancelled", "command": "assign"},
    }
    assert await ride_events(session_factory, trip.ride_id) == before


async def test_accepting_an_offer_of_a_cancelled_search_is_409(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)
    await expect_ok(client, trip, "cancel")

    response = await accept(client, trip)

    assert response.status_code == 409, response.text
    assert error_of(response)["code"] == "invalid_ride_transition"
    ride = await dispatcher.ride(trip.ride_id)
    assert (ride.status.value, ride.driver_id) == ("cancelled", None)
    assert await commands_of(session_factory, trip.ride_id) == ["cancel"]


# Release


@pytest.mark.parametrize("status", RELEASABLE)
async def test_release_starts_a_new_search_without_the_releasing_driver(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
    status: str,
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    other = await driver_factory.driver("other_driver", location=OTHER_SPOT)
    first_search = await dispatcher.ride(trip.ride_id)
    clock.advance(STEP)

    response = await send(
        client, trip.ride_id, "release", trip.driver, json={"reason": "flat tyre"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["driver_id"]) == ("searching", None)
    assert (body["assigned_at"], body["arrived_at"]) == (None, None)
    ride = await dispatcher.ride(trip.ride_id)
    assert ride.search_started_at == clock.now() > first_search.search_started_at
    assert ride.search_deadline == clock.now() + timedelta(seconds=180)
    pending = await dispatcher.pending(trip.ride_id)
    assert pending is not None
    assert pending.driver_id == other
    [own] = await dispatcher.offers(trip.ride_id, driver_id=trip.driver_id)
    assert own.status is OfferStatus.ACCEPTED
    events = await ride_events(session_factory, trip.ride_id)
    assert events[-1] == Event(status, "searching", "release", trip.driver_id, "flat tyre")
    gone = await read_ride(client, trip.ride_id, trip.driver)
    assert gone.status_code == 404


async def test_released_driver_is_not_asked_again_even_when_nobody_else_is_there(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    clock.advance(STEP)

    response = await send(client, trip.ride_id, "release", trip.driver)

    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["driver_id"]) == ("no_driver", None)
    assert await ride_events(session_factory, trip.ride_id) == [
        Event("searching", "assigned", "assign", trip.driver_id, None),
        Event("assigned", "searching", "release", trip.driver_id, "flat tyre"),
        Event("searching", "no_driver", "mark_no_driver", None, None),
    ]


def released_snapshot(body: dict[str, Any]) -> tuple[Any, ...]:
    return (
        body["status"],
        body["driver_id"],
        body["assigned_at"],
        body["cancelled_at"],
        body["cancel_reason"],
    )


async def test_release_answer_does_not_show_a_later_cancel(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The passenger cancels between the release commit and its search step."""
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    original = dispatch.process_ride

    async def passenger_cancels_first(
        db: AsyncSession, ride_id: uuid.UUID, **kwargs: Any
    ) -> Ride | None:
        async with session_factory() as session:
            await lifecycle.execute_command(
                session,
                ride_id,
                RideCommand.CANCEL,
                user_id=trip.passenger_id,
                role=UserRole.PASSENGER,
                reason="private note",
                clock=dispatcher.clock,
            )
        return await original(db, ride_id, **kwargs)

    monkeypatch.setattr(dispatch, "process_ride", passenger_cancels_first)
    response = await send(client, trip.ride_id, "release", trip.driver)

    assert response.status_code == 200, response.text
    assert released_snapshot(response.json()) == ("searching", None, None, None, None)
    assert "private note" not in response.text
    assert (await dispatcher.ride(trip.ride_id)).status.value == "cancelled"


async def test_release_answer_does_not_show_the_next_driver(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another driver gets the offer and accepts before the releaser's answer is built."""
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    other = await driver_factory.driver("other_driver", location=OTHER_SPOT)
    original = dispatch.process_ride

    async def other_driver_accepts_meanwhile(
        db: AsyncSession, ride_id: uuid.UUID, **kwargs: Any
    ) -> Ride | None:
        await original(db, ride_id, **kwargs)
        offer = await dispatcher.pending(ride_id)
        assert offer is not None
        await dispatcher.accept(offer.id, other)
        return await original(db, ride_id, **kwargs)

    monkeypatch.setattr(dispatch, "process_ride", other_driver_accepts_meanwhile)
    response = await send(client, trip.ride_id, "release", trip.driver)

    assert response.status_code == 200, response.text
    assert released_snapshot(response.json()) == ("searching", None, None, None, None)
    assert str(other) not in response.text
    ride = await dispatcher.ride(trip.ride_id)
    assert (ride.status.value, ride.driver_id) == ("assigned", other)


async def test_release_answers_even_if_the_search_step_fails(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)

    async def broken(*args: object, **kwargs: object) -> Ride | None:
        raise RuntimeError("dispatch is down")

    monkeypatch.setattr(dispatch, "process_ride", broken)
    response = await send(client, trip.ride_id, "release", trip.driver)

    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["driver_id"]) == ("searching", None)


@pytest.mark.parametrize(
    "body", [None, {}, {"reason": ""}, {"reason": " "}, {"reason": "x" * 201}, {"reason": "a\tb"}]
)
async def test_release_needs_a_short_plain_reason(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    body: dict[str, Any] | None,
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)
    driver = await login_as(client, trip.driver)

    response = await client.post(
        f"{ride_url(trip.ride_id)}/release", json=body, headers=driver.csrf_headers
    )

    assert response.status_code == 422, response.text
    assert error_of(response)["code"] == "validation_error"
    assert (await dispatcher.ride(trip.ride_id)).status.value == "assigned"


async def test_command_bodies_reject_unknown_fields(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("assigned", client, driver_factory, dispatcher)

    response = await send(
        client, trip.ride_id, "release", trip.driver, json={"reason": "x", "status": "completed"}
    )

    assert response.status_code == 422, response.text


# System transitions in the history


async def test_search_without_drivers_records_no_driver(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("no_driver", client, driver_factory, dispatcher)

    assert await ride_events(session_factory, trip.ride_id) == [
        Event("searching", "no_driver", "mark_no_driver", None, None)
    ]


async def test_spent_search_budget_records_no_driver_once(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    trip = await trip_in("searching", client, driver_factory, dispatcher)

    clock.advance(timedelta(seconds=181))
    await dispatcher.process_due()
    await dispatcher.process_due()

    assert (await dispatcher.ride(trip.ride_id)).status.value == "no_driver"
    assert await ride_events(session_factory, trip.ride_id) == [
        Event("searching", "no_driver", "mark_no_driver", None, None)
    ]


# Completion hook (the payment itself is opened with the order, ADR 0010)


class CompletionRecorder:
    """Stands in for the completion hook, an extension point inside the completion transaction.

    With ``fail`` it first writes and flushes a row of its own, then raises:
    that row must vanish with the rollback.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str, datetime]] = []
        self.fail = False
        self.written: uuid.UUID | None = None

    async def __call__(self, session: AsyncSession, ride: Ride, now: datetime) -> None:
        assert session.in_transaction()
        self.calls.append((ride.id, ride.status.value, now))
        if self.fail:
            row = RideEvent(
                id=uuid.uuid4(),
                ride_id=ride.id,
                from_status=RideStatus.IN_PROGRESS,
                to_status=RideStatus.COMPLETED,
                command=RideCommand.COMPLETE,
                actor_id=None,
                reason="written by the completion hook",
                created_at=now,
            )
            session.add(row)
            await session.flush()
            self.written = row.id
            raise RuntimeError("completion hook failed")


@pytest.fixture
def completion(app: FastAPI) -> CompletionRecorder:
    recorder = CompletionRecorder()
    app.state.ride_completion_hook = recorder
    return recorder


async def test_complete_calls_the_completion_hook_once_in_its_transaction(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    completion: CompletionRecorder,
    clock: ManualClock,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    await expect_ok(client, trip, "complete")
    await expect_ok(client, trip, "complete")

    assert completion.calls == [(trip.ride_id, "completed", clock.now())]


async def test_failing_completion_hook_rolls_the_completion_back(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    completion: CompletionRecorder,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    completion.fail = True

    # The app answers 500; the test transport re-raises the unhandled error.
    with pytest.raises(RuntimeError, match="completion hook failed"):
        await send(client, trip.ride_id, "complete", trip.driver)

    ride = await dispatcher.ride(trip.ride_id)
    assert (ride.status.value, ride.completed_at) == ("in_progress", None)
    assert "complete" not in await commands_of(session_factory, trip.ride_id)
    assert completion.written is not None
    async with session_factory() as session, read_transaction(session):
        assert await session.get(RideEvent, completion.written) is None
