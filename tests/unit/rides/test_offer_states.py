import itertools
from datetime import UTC, datetime, timedelta

import pytest

from taxi_service.modules.rides.exceptions import InvalidOfferTransitionError
from taxi_service.modules.rides.states import (
    TERMINAL_OFFER_STATUSES,
    OfferCommand,
    OfferStatus,
    can_accept_offer,
    is_offer_command_already_applied,
    is_offer_expired,
    next_offer_status,
)

OS = OfferStatus
OC = OfferCommand

EXPIRES_AT = datetime(2026, 11, 3, 12, 0, 30, tzinfo=UTC)
TARGET: dict[OfferCommand, OfferStatus] = {
    OC.ACCEPT: OS.ACCEPTED,
    OC.REJECT: OS.REJECTED,
    OC.EXPIRE: OS.EXPIRED,
    OC.REVOKE: OS.REVOKED,
}


@pytest.mark.parametrize(("command", "expected"), list(TARGET.items()))
def test_pending_offer_moves_to_its_decision(command: OfferCommand, expected: OfferStatus) -> None:
    assert next_offer_status(OS.PENDING, command) is expected


@pytest.mark.parametrize(
    ("current", "command"), list(itertools.product(sorted(TERMINAL_OFFER_STATUSES), OfferCommand))
)
def test_decided_offer_does_not_change(current: OfferStatus, command: OfferCommand) -> None:
    with pytest.raises(InvalidOfferTransitionError) as caught:
        next_offer_status(current, command)

    assert caught.value.status_code == 409
    assert caught.value.code == "invalid_offer_transition"
    assert caught.value.details == {"current_status": current.value, "command": command.value}


def test_decided_offer_matrix_is_not_empty() -> None:
    assert len(TERMINAL_OFFER_STATUSES) == 4


def test_offer_is_acceptable_before_the_deadline() -> None:
    now = EXPIRES_AT - timedelta(microseconds=1)

    assert not is_offer_expired(now=now, expires_at=EXPIRES_AT)
    assert can_accept_offer(OS.PENDING, now=now, expires_at=EXPIRES_AT)


def test_offer_is_not_acceptable_exactly_at_the_deadline() -> None:
    assert is_offer_expired(now=EXPIRES_AT, expires_at=EXPIRES_AT)
    assert not can_accept_offer(OS.PENDING, now=EXPIRES_AT, expires_at=EXPIRES_AT)


def test_offer_is_not_acceptable_after_the_deadline() -> None:
    now = EXPIRES_AT + timedelta(seconds=1)

    assert not can_accept_offer(OS.PENDING, now=now, expires_at=EXPIRES_AT)


@pytest.mark.parametrize("status", sorted(TERMINAL_OFFER_STATUSES))
def test_decided_offer_is_not_acceptable_even_in_time(status: OfferStatus) -> None:
    now = EXPIRES_AT - timedelta(seconds=10)

    assert not can_accept_offer(status, now=now, expires_at=EXPIRES_AT)


@pytest.mark.parametrize(
    ("now", "expires_at"),
    [
        (EXPIRES_AT.replace(tzinfo=None), EXPIRES_AT),
        (EXPIRES_AT, EXPIRES_AT.replace(tzinfo=None)),
    ],
)
def test_deadline_needs_timezone_aware_times(now: datetime, expires_at: datetime) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        is_offer_expired(now=now, expires_at=expires_at)


@pytest.mark.parametrize(("command", "current"), [(c, s) for c, s in TARGET.items()])
def test_repeated_offer_decision_is_already_applied(
    command: OfferCommand, current: OfferStatus
) -> None:
    assert is_offer_command_already_applied(current, command)


@pytest.mark.parametrize(
    ("current", "command"),
    [
        (current, command)
        for current, command in itertools.product(OfferStatus, OfferCommand)
        if TARGET[command] is not current
    ],
)
def test_other_offer_pairs_are_not_already_applied(
    current: OfferStatus, command: OfferCommand
) -> None:
    assert not is_offer_command_already_applied(current, command)
