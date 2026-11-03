import itertools

import pytest

from taxi_service.modules.rides.exceptions import (
    InvalidRideTransitionError,
    RideCommandForbiddenError,
    RideNotFoundError,
)
from taxi_service.modules.rides.states import (
    IDEMPOTENT_RIDE_COMMANDS,
    SYSTEM_ACTOR,
    Actor,
    CommandOutcome,
    RideCommand,
    RideStatus,
    is_already_applied,
    resolve_command,
)
from taxi_service.modules.users.models import UserRole

S = RideStatus
C = RideCommand

PASSENGER_OWNER = Actor(role=UserRole.PASSENGER, is_ride_passenger=True)
ASSIGNED_DRIVER = Actor(role=UserRole.DRIVER, is_assigned_driver=True)
OTHER_DRIVER = Actor(role=UserRole.DRIVER)
ADMIN = Actor(role=UserRole.ADMIN)

APPLIED: dict[RideCommand, RideStatus] = {
    C.ARRIVE: S.ARRIVED,
    C.START: S.IN_PROGRESS,
    C.COMPLETE: S.COMPLETED,
    C.CANCEL: S.CANCELLED,
    C.MARK_NO_DRIVER: S.NO_DRIVER,
}

RIGHTFUL_ACTOR: dict[RideCommand, Actor] = {
    C.ASSIGN: SYSTEM_ACTOR,
    C.MARK_NO_DRIVER: SYSTEM_ACTOR,
    C.CANCEL: PASSENGER_OWNER,
    C.ARRIVE: ASSIGNED_DRIVER,
    C.START: ASSIGNED_DRIVER,
    C.COMPLETE: ASSIGNED_DRIVER,
    C.RELEASE: ASSIGNED_DRIVER,
}


def test_idempotent_commands() -> None:
    assert set(APPLIED) == IDEMPOTENT_RIDE_COMMANDS


@pytest.mark.parametrize(("command", "current"), list(APPLIED.items()))
def test_repeated_command_is_recognised_as_already_applied(
    command: RideCommand, current: RideStatus
) -> None:
    assert is_already_applied(current, command)


@pytest.mark.parametrize(
    ("current", "command"),
    [
        (current, command)
        for current, command in itertools.product(RideStatus, RideCommand)
        if APPLIED.get(command) is not current
    ],
)
def test_other_pairs_are_not_already_applied(current: RideStatus, command: RideCommand) -> None:
    assert not is_already_applied(current, command)


def test_assign_is_not_idempotent_at_ride_level() -> None:
    # The ride does not know which driver accepted; the offer decides (T06).
    assert not is_already_applied(S.ASSIGNED, C.ASSIGN)


def test_release_is_not_idempotent_because_searching_is_ambiguous() -> None:
    assert not is_already_applied(S.SEARCHING, C.RELEASE)


@pytest.mark.parametrize(("command", "current"), list(APPLIED.items()))
def test_repeat_by_the_rightful_actor_keeps_the_status(
    command: RideCommand, current: RideStatus
) -> None:
    outcome = resolve_command(current, command, RIGHTFUL_ACTOR[command])

    assert outcome == CommandOutcome(status=current, changed=False)


def test_first_command_changes_the_status() -> None:
    outcome = resolve_command(S.IN_PROGRESS, C.COMPLETE, ASSIGNED_DRIVER)

    assert outcome == CommandOutcome(status=S.COMPLETED, changed=True)


def test_repeated_complete_by_a_stranger_is_not_found() -> None:
    with pytest.raises(RideNotFoundError):
        resolve_command(S.COMPLETED, C.COMPLETE, OTHER_DRIVER)


def test_repeated_cancel_by_admin_is_forbidden() -> None:
    with pytest.raises(RideCommandForbiddenError):
        resolve_command(S.CANCELLED, C.CANCEL, ADMIN)


@pytest.mark.parametrize(
    ("current", "command"),
    [
        (S.IN_PROGRESS, C.ARRIVE),
        (S.COMPLETED, C.CANCEL),
        (S.NO_DRIVER, C.CANCEL),
        (S.CANCELLED, C.COMPLETE),
        (S.SEARCHING, C.RELEASE),
        (S.ASSIGNED, C.ASSIGN),
    ],
)
def test_resolve_still_rejects_invalid_transitions(
    current: RideStatus, command: RideCommand
) -> None:
    with pytest.raises(InvalidRideTransitionError):
        resolve_command(current, command, RIGHTFUL_ACTOR[command])
