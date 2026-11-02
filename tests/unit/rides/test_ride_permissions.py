import itertools
from typing import Literal

import pytest

from taxi_service.modules.rides.exceptions import (
    RideCommandForbiddenError,
    RideNotFoundError,
)
from taxi_service.modules.rides.states import (
    SYSTEM_ACTOR,
    Actor,
    RideCommand,
    RideStatus,
    next_status,
)
from taxi_service.modules.users.models import UserRole

S = RideStatus
C = RideCommand
Outcome = Literal["allowed", "forbidden", "not_found"]

PASSENGER_OWNER = Actor(role=UserRole.PASSENGER, is_ride_passenger=True)
OTHER_PASSENGER = Actor(role=UserRole.PASSENGER)
ASSIGNED_DRIVER = Actor(role=UserRole.DRIVER, is_assigned_driver=True)
OTHER_DRIVER = Actor(role=UserRole.DRIVER)
ADMIN = Actor(role=UserRole.ADMIN)

ACTORS: dict[str, Actor] = {
    "system": SYSTEM_ACTOR,
    "passenger_owner": PASSENGER_OWNER,
    "other_passenger": OTHER_PASSENGER,
    "assigned_driver": ASSIGNED_DRIVER,
    "other_driver": OTHER_DRIVER,
    "admin": ADMIN,
}

RIGHTFUL: dict[RideCommand, str] = {
    C.ASSIGN: "system",
    C.MARK_NO_DRIVER: "system",
    C.CANCEL: "passenger_owner",
    C.ARRIVE: "assigned_driver",
    C.START: "assigned_driver",
    C.COMPLETE: "assigned_driver",
    C.RELEASE: "assigned_driver",
}

# A status in which the command is a valid transition, so only access decides.
APPLICABLE_STATUS: dict[RideCommand, RideStatus] = {
    C.ASSIGN: S.SEARCHING,
    C.MARK_NO_DRIVER: S.SEARCHING,
    C.CANCEL: S.ARRIVED,
    C.ARRIVE: S.ASSIGNED,
    C.START: S.ARRIVED,
    C.COMPLETE: S.IN_PROGRESS,
    C.RELEASE: S.ASSIGNED,
}

STRANGERS = {"other_passenger", "other_driver"}


def expected_outcome(command: RideCommand, actor_name: str) -> Outcome:
    if RIGHTFUL[command] == actor_name:
        return "allowed"
    if actor_name in STRANGERS:
        return "not_found"
    return "forbidden"


MATRIX = [
    (command, actor_name, expected_outcome(command, actor_name))
    for command, actor_name in itertools.product(RideCommand, ACTORS)
]


@pytest.mark.parametrize(("command", "actor_name", "outcome"), MATRIX)
def test_command_access_matrix(command: RideCommand, actor_name: str, outcome: Outcome) -> None:
    current = APPLICABLE_STATUS[command]
    actor = ACTORS[actor_name]

    if outcome == "allowed":
        next_status(current, command, actor)
    elif outcome == "not_found":
        with pytest.raises(RideNotFoundError):
            next_status(current, command, actor)
    else:
        with pytest.raises(RideCommandForbiddenError):
            next_status(current, command, actor)


def test_stranger_sees_ride_not_found_without_details() -> None:
    with pytest.raises(RideNotFoundError) as caught:
        next_status(S.SEARCHING, C.CANCEL, OTHER_PASSENGER)

    assert caught.value.status_code == 404
    assert caught.value.code == "ride_not_found"
    assert caught.value.details == {}


def test_forbidden_command_names_only_the_command() -> None:
    with pytest.raises(RideCommandForbiddenError) as caught:
        next_status(S.ASSIGNED, C.ARRIVE, PASSENGER_OWNER)

    assert caught.value.status_code == 403
    assert caught.value.code == "ride_command_forbidden"
    assert caught.value.details == {"command": "arrive"}


@pytest.mark.parametrize("command", list(RideCommand))
def test_admin_does_not_drive_the_lifecycle(command: RideCommand) -> None:
    with pytest.raises(RideCommandForbiddenError):
        next_status(APPLICABLE_STATUS[command], command, ADMIN)


@pytest.mark.parametrize(
    "actor", [PASSENGER_OWNER, ASSIGNED_DRIVER, ADMIN, OTHER_DRIVER, OTHER_PASSENGER]
)
@pytest.mark.parametrize("command", [C.ASSIGN, C.MARK_NO_DRIVER])
def test_system_commands_are_not_available_to_users(command: RideCommand, actor: Actor) -> None:
    with pytest.raises((RideCommandForbiddenError, RideNotFoundError)):
        next_status(S.SEARCHING, command, actor)


@pytest.mark.parametrize("command", [C.ARRIVE, C.START, C.COMPLETE, C.RELEASE, C.CANCEL])
def test_system_cannot_issue_user_commands(command: RideCommand) -> None:
    with pytest.raises(RideCommandForbiddenError):
        next_status(APPLICABLE_STATUS[command], command, SYSTEM_ACTOR)


@pytest.mark.parametrize("current", list(RideStatus))
def test_stranger_learns_nothing_about_the_status(current: RideStatus) -> None:
    with pytest.raises(RideNotFoundError):
        next_status(current, C.COMPLETE, OTHER_DRIVER)


@pytest.mark.parametrize("current", [S.IN_PROGRESS, S.COMPLETED, S.NO_DRIVER])
def test_access_is_checked_before_the_transition(current: RideStatus) -> None:
    with pytest.raises(RideCommandForbiddenError):
        next_status(current, C.ARRIVE, PASSENGER_OWNER)


@pytest.mark.parametrize(
    "fields",
    [
        {"role": UserRole.DRIVER, "is_ride_passenger": True},
        {"role": UserRole.ADMIN, "is_ride_passenger": True},
        {"role": UserRole.PASSENGER, "is_assigned_driver": True},
        {"role": UserRole.ADMIN, "is_assigned_driver": True},
        {"role": None, "is_ride_passenger": True},
        {"role": None, "is_assigned_driver": True},
    ],
)
def test_actor_flags_must_match_the_role(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Actor"):
        Actor(**fields)  # type: ignore[arg-type]


def test_system_actor_is_recognised() -> None:
    assert SYSTEM_ACTOR.is_system
    assert not PASSENGER_OWNER.is_system
