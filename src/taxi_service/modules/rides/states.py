from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from taxi_service.modules.rides.exceptions import (
    InvalidOfferTransitionError,
    InvalidRideTransitionError,
    RideCommandForbiddenError,
    RideNotFoundError,
)
from taxi_service.modules.users.models import UserRole


class RideStatus(StrEnum):
    SEARCHING = "searching"
    ASSIGNED = "assigned"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_DRIVER = "no_driver"


class OfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


PRE_START_RIDE_STATUSES: Final = frozenset(
    {RideStatus.SEARCHING, RideStatus.ASSIGNED, RideStatus.ARRIVED}
)
ACTIVE_RIDE_STATUSES: Final = PRE_START_RIDE_STATUSES | {RideStatus.IN_PROGRESS}
TERMINAL_RIDE_STATUSES: Final = frozenset(RideStatus) - ACTIVE_RIDE_STATUSES
TERMINAL_OFFER_STATUSES: Final = frozenset(OfferStatus) - {OfferStatus.PENDING}


class RideCommand(StrEnum):
    ASSIGN = "assign"
    ARRIVE = "arrive"
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"
    RELEASE = "release"
    MARK_NO_DRIVER = "mark_no_driver"


@dataclass(frozen=True, slots=True, kw_only=True)
class Actor:
    role: UserRole | None
    is_ride_passenger: bool = False
    is_assigned_driver: bool = False

    def __post_init__(self) -> None:
        if self.is_ride_passenger and self.role is not UserRole.PASSENGER:
            raise ValueError("Actor: only a passenger can be the ride's passenger")
        if self.is_assigned_driver and self.role is not UserRole.DRIVER:
            raise ValueError("Actor: only a driver can be the ride's assigned driver")

    @property
    def is_system(self) -> bool:
        return self.role is None

    @property
    def is_participant(self) -> bool:
        return self.is_ride_passenger or self.is_assigned_driver


SYSTEM_ACTOR: Final = Actor(role=None)

SYSTEM_COMMANDS: Final = frozenset({RideCommand.ASSIGN, RideCommand.MARK_NO_DRIVER})
PASSENGER_COMMANDS: Final = frozenset({RideCommand.CANCEL})
DRIVER_COMMANDS: Final = frozenset(
    {RideCommand.ARRIVE, RideCommand.START, RideCommand.COMPLETE, RideCommand.RELEASE}
)


def authorize_command(command: RideCommand, actor: Actor) -> None:
    if actor.is_system:
        allowed = command in SYSTEM_COMMANDS
    else:
        if not actor.is_participant and actor.role is not UserRole.ADMIN:
            raise RideNotFoundError
        allowed = (actor.is_ride_passenger and command in PASSENGER_COMMANDS) or (
            actor.is_assigned_driver and command in DRIVER_COMMANDS
        )
    if not allowed:
        raise RideCommandForbiddenError(command=command.value)


_TRANSITIONS: Final[Mapping[RideCommand, Mapping[RideStatus, RideStatus]]] = {
    RideCommand.ASSIGN: {RideStatus.SEARCHING: RideStatus.ASSIGNED},
    RideCommand.ARRIVE: {RideStatus.ASSIGNED: RideStatus.ARRIVED},
    RideCommand.START: {RideStatus.ARRIVED: RideStatus.IN_PROGRESS},
    RideCommand.COMPLETE: {RideStatus.IN_PROGRESS: RideStatus.COMPLETED},
    RideCommand.MARK_NO_DRIVER: {RideStatus.SEARCHING: RideStatus.NO_DRIVER},
    RideCommand.CANCEL: {status: RideStatus.CANCELLED for status in PRE_START_RIDE_STATUSES},
    RideCommand.RELEASE: {
        RideStatus.ASSIGNED: RideStatus.SEARCHING,
        RideStatus.ARRIVED: RideStatus.SEARCHING,
    },
}


def next_status(current: RideStatus, command: RideCommand, actor: Actor) -> RideStatus:
    authorize_command(command, actor)
    target = _TRANSITIONS[command].get(current)
    if target is None:
        raise InvalidRideTransitionError(current_status=current.value, command=command.value)
    return target


_APPLIED_STATUS: Final[Mapping[RideCommand, RideStatus]] = {
    RideCommand.ARRIVE: RideStatus.ARRIVED,
    RideCommand.START: RideStatus.IN_PROGRESS,
    RideCommand.COMPLETE: RideStatus.COMPLETED,
    RideCommand.CANCEL: RideStatus.CANCELLED,
    RideCommand.MARK_NO_DRIVER: RideStatus.NO_DRIVER,
}
IDEMPOTENT_RIDE_COMMANDS: Final = frozenset(_APPLIED_STATUS)


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandOutcome:
    status: RideStatus
    changed: bool


def is_already_applied(current: RideStatus, command: RideCommand) -> bool:
    return _APPLIED_STATUS.get(command) is current


def resolve_command(current: RideStatus, command: RideCommand, actor: Actor) -> CommandOutcome:
    authorize_command(command, actor)
    if is_already_applied(current, command):
        return CommandOutcome(status=current, changed=False)
    return CommandOutcome(status=next_status(current, command, actor), changed=True)


class OfferCommand(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    EXPIRE = "expire"
    REVOKE = "revoke"


_OFFER_DECISION: Final[Mapping[OfferCommand, OfferStatus]] = {
    OfferCommand.ACCEPT: OfferStatus.ACCEPTED,
    OfferCommand.REJECT: OfferStatus.REJECTED,
    OfferCommand.EXPIRE: OfferStatus.EXPIRED,
    OfferCommand.REVOKE: OfferStatus.REVOKED,
}


def next_offer_status(current: OfferStatus, command: OfferCommand) -> OfferStatus:
    if current is not OfferStatus.PENDING:
        raise InvalidOfferTransitionError(current_status=current.value, command=command.value)
    return _OFFER_DECISION[command]


def is_offer_expired(*, now: datetime, expires_at: datetime) -> bool:
    if now.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("Offer deadline check needs timezone-aware datetimes")
    return now >= expires_at


def can_accept_offer(status: OfferStatus, *, now: datetime, expires_at: datetime) -> bool:
    expired = is_offer_expired(now=now, expires_at=expires_at)
    return status is OfferStatus.PENDING and not expired


def is_offer_command_already_applied(current: OfferStatus, command: OfferCommand) -> bool:
    return _OFFER_DECISION[command] is current
