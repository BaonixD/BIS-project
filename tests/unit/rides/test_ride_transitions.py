import itertools

import pytest

from taxi_service.modules.rides import states
from taxi_service.modules.rides.exceptions import InvalidRideTransitionError
from taxi_service.modules.rides.states import (
    SYSTEM_ACTOR,
    TERMINAL_RIDE_STATUSES,
    Actor,
    RideCommand,
    RideStatus,
    next_status,
)
from taxi_service.modules.users.models import UserRole

S = RideStatus
C = RideCommand

PASSENGER_OWNER = Actor(role=UserRole.PASSENGER, is_ride_passenger=True)
ASSIGNED_DRIVER = Actor(role=UserRole.DRIVER, is_assigned_driver=True)

RIGHTFUL_ACTOR: dict[RideCommand, Actor] = {
    C.ASSIGN: SYSTEM_ACTOR,
    C.MARK_NO_DRIVER: SYSTEM_ACTOR,
    C.CANCEL: PASSENGER_OWNER,
    C.ARRIVE: ASSIGNED_DRIVER,
    C.START: ASSIGNED_DRIVER,
    C.COMPLETE: ASSIGNED_DRIVER,
    C.RELEASE: ASSIGNED_DRIVER,
}

ALLOWED: dict[tuple[RideStatus, RideCommand], RideStatus] = {
    (S.SEARCHING, C.ASSIGN): S.ASSIGNED,
    (S.ASSIGNED, C.ARRIVE): S.ARRIVED,
    (S.ARRIVED, C.START): S.IN_PROGRESS,
    (S.IN_PROGRESS, C.COMPLETE): S.COMPLETED,
    (S.SEARCHING, C.MARK_NO_DRIVER): S.NO_DRIVER,
    (S.SEARCHING, C.CANCEL): S.CANCELLED,
    (S.ASSIGNED, C.CANCEL): S.CANCELLED,
    (S.ARRIVED, C.CANCEL): S.CANCELLED,
    (S.ASSIGNED, C.RELEASE): S.SEARCHING,
    (S.ARRIVED, C.RELEASE): S.SEARCHING,
}

FORBIDDEN = [pair for pair in itertools.product(RideStatus, RideCommand) if pair not in ALLOWED]


def test_matrix_covers_every_status_and_command() -> None:
    assert len(ALLOWED) + len(FORBIDDEN) == len(RideStatus) * len(RideCommand)
    assert set(RIGHTFUL_ACTOR) == set(RideCommand)


@pytest.mark.parametrize(("current", "command", "expected"), [(*k, v) for k, v in ALLOWED.items()])
def test_allowed_transition(
    current: RideStatus, command: RideCommand, expected: RideStatus
) -> None:
    assert next_status(current, command, RIGHTFUL_ACTOR[command]) is expected


@pytest.mark.parametrize(("current", "command"), FORBIDDEN)
def test_forbidden_transition_is_a_conflict(current: RideStatus, command: RideCommand) -> None:
    with pytest.raises(InvalidRideTransitionError) as caught:
        next_status(current, command, RIGHTFUL_ACTOR[command])

    error = caught.value
    assert error.status_code == 409
    assert error.code == "invalid_ride_transition"
    assert error.details == {"current_status": current.value, "command": command.value}


@pytest.mark.parametrize(
    ("current", "command"),
    list(itertools.product([S.COMPLETED, S.CANCELLED, S.NO_DRIVER], RideCommand)),
)
def test_terminal_ride_never_comes_back(current: RideStatus, command: RideCommand) -> None:
    assert current in TERMINAL_RIDE_STATUSES
    with pytest.raises(InvalidRideTransitionError):
        next_status(current, command, RIGHTFUL_ACTOR[command])


def test_ride_in_progress_cannot_be_cancelled() -> None:
    with pytest.raises(InvalidRideTransitionError):
        next_status(S.IN_PROGRESS, C.CANCEL, PASSENGER_OWNER)


def test_ride_in_progress_cannot_be_released() -> None:
    with pytest.raises(InvalidRideTransitionError):
        next_status(S.IN_PROGRESS, C.RELEASE, ASSIGNED_DRIVER)


@pytest.mark.parametrize("current", [S.ASSIGNED, S.ARRIVED])
def test_release_restarts_the_search(current: RideStatus) -> None:
    assert next_status(current, C.RELEASE, ASSIGNED_DRIVER) is S.SEARCHING


def test_module_docstring_table_matches_the_rules() -> None:
    assert states.__doc__ is not None
    rows = [line.split() for line in states.__doc__.splitlines()]
    header = next(row for row in rows if row[:1] == ["current"])
    start = rows.index(header)
    table = {row[0]: row[1:] for row in rows[start + 2 : start + 2 + len(RideStatus)]}

    documented = {
        (S(status), C(command)): cell
        for status, cells in table.items()
        for command, cell in zip(header[1:], cells, strict=True)
    }
    expected = {pair: target.value for pair, target in ALLOWED.items()}
    expected |= dict.fromkeys(FORBIDDEN, "409")
    assert documented == expected


def test_happy_path_reaches_completed() -> None:
    status = S.SEARCHING
    for command in (C.ASSIGN, C.ARRIVE, C.START, C.COMPLETE):
        status = next_status(status, command, RIGHTFUL_ACTOR[command])

    assert status is S.COMPLETED
