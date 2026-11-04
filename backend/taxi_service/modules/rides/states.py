"""Pure lifecycle rules of a ride and of a driver offer (MVP_SPEC §6); no database, no HTTP.

Ride statuses and commands::

    searching   --assign*-------->  assigned       (* system: an offer was accepted)
    assigned    --arrive--------->  arrived
    arrived     --start---------->  in_progress
    in_progress --complete------->  completed
    searching   --mark_no_driver*>  no_driver      (* system: no candidates / budget spent)
    searching / assigned / arrived  --cancel-->   cancelled
    assigned / arrived              --release-->  searching   (driver gave the ride up)

=========== ======== ======= =========== ========= ========= ========= ==============
current     assign   arrive  start       complete  cancel    release   mark_no_driver
=========== ======== ======= =========== ========= ========= ========= ==============
searching   assigned 409     409         409       cancelled 409       no_driver
assigned    409      arrived 409         409       cancelled searching 409
arrived     409      409     in_progress 409       cancelled searching 409
in_progress 409      409     409         completed 409       409       409
completed   409      409     409         409       409       409       409
cancelled   409      409     409         409       409       409       409
no_driver   409      409     409         409       409       409       409
=========== ======== ======= =========== ========= ========= ========= ==============

``completed``, ``cancelled`` and ``no_driver`` are terminal; ``in_progress`` cannot be
cancelled (no emergency close in the MVP). 409 is ``invalid_ride_transition``.

Who may issue a command (checked *before* the status, see ``authorize_command``):

============================== ==========================================================
command                        initiator
============================== ==========================================================
assign, mark_no_driver         ``SYSTEM_ACTOR`` only (dispatch, T06)
cancel                         the ride's passenger
arrive, start, complete,       the ride's assigned driver
release
============================== ==========================================================

Admin reads rides but does not drive the lifecycle in the MVP (403). Users who are not
participants of the ride get 404 ``ride_not_found``.

A driver offer is a separate entity: ``pending`` moves once to ``accepted``, ``rejected``,
``expired`` or ``revoked``; all four are terminal. Acceptance requires ``now < expires_at``.
"""

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


class RideCommand(StrEnum):
    ASSIGN = "assign"
    ARRIVE = "arrive"
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"
    RELEASE = "release"
    MARK_NO_DRIVER = "mark_no_driver"


PRE_START_RIDE_STATUSES: Final = frozenset(
    {RideStatus.SEARCHING, RideStatus.ASSIGNED, RideStatus.ARRIVED}
)
ACTIVE_RIDE_STATUSES: Final = PRE_START_RIDE_STATUSES | {RideStatus.IN_PROGRESS}
TERMINAL_RIDE_STATUSES: Final = frozenset(RideStatus) - ACTIVE_RIDE_STATUSES

SYSTEM_COMMANDS: Final = frozenset({RideCommand.ASSIGN, RideCommand.MARK_NO_DRIVER})
PASSENGER_COMMANDS: Final = frozenset({RideCommand.CANCEL})
DRIVER_COMMANDS: Final = frozenset(
    {RideCommand.ARRIVE, RideCommand.START, RideCommand.COMPLETE, RideCommand.RELEASE}
)

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

# Status that proves an idempotent command was already applied to this ride.
_APPLIED_STATUS: Final[Mapping[RideCommand, RideStatus]] = {
    RideCommand.ARRIVE: RideStatus.ARRIVED,
    RideCommand.START: RideStatus.IN_PROGRESS,
    RideCommand.COMPLETE: RideStatus.COMPLETED,
    RideCommand.CANCEL: RideStatus.CANCELLED,
    RideCommand.MARK_NO_DRIVER: RideStatus.NO_DRIVER,
}
IDEMPOTENT_RIDE_COMMANDS: Final = frozenset(_APPLIED_STATUS)


@dataclass(frozen=True, slots=True, kw_only=True)
class Actor:
    """``role=None`` is the system; use ``SYSTEM_ACTOR``."""

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


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandOutcome:
    """``changed=False`` means a repeat: return the stored result, run no side effects."""

    status: RideStatus
    changed: bool


def authorize_command(command: RideCommand, actor: Actor) -> None:
    """Before the status: a non-participant gets 404 so the ride's status stays hidden."""
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


def next_status(current: RideStatus, command: RideCommand, actor: Actor) -> RideStatus:
    """Strict: a repeat on the target status is 409 too."""
    authorize_command(command, actor)
    return _transition(current, command)


def is_already_applied(current: RideStatus, command: RideCommand) -> bool:
    """``assign`` and ``release`` are never repeats: ``searching`` is also the initial status."""
    return _APPLIED_STATUS.get(command) is current


def resolve_command(current: RideStatus, command: RideCommand, actor: Actor) -> CommandOutcome:
    """Access check, then a repeat is answered without change, else ``next_status`` rules."""
    authorize_command(command, actor)
    if is_already_applied(current, command):
        return CommandOutcome(status=current, changed=False)
    return CommandOutcome(status=_transition(current, command), changed=True)


def _transition(current: RideStatus, command: RideCommand) -> RideStatus:
    target = _TRANSITIONS[command].get(current)
    if target is None:
        raise InvalidRideTransitionError(current_status=current.value, command=command.value)
    return target


class OfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class OfferCommand(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    EXPIRE = "expire"
    REVOKE = "revoke"


TERMINAL_OFFER_STATUSES: Final = frozenset(OfferStatus) - {OfferStatus.PENDING}

_OFFER_DECISION: Final[Mapping[OfferCommand, OfferStatus]] = {
    OfferCommand.ACCEPT: OfferStatus.ACCEPTED,
    OfferCommand.REJECT: OfferStatus.REJECTED,
    OfferCommand.EXPIRE: OfferStatus.EXPIRED,
    OfferCommand.REVOKE: OfferStatus.REVOKED,
}


def next_offer_status(current: OfferStatus, command: OfferCommand) -> OfferStatus:
    """Time is not checked here: an accept must also pass ``can_accept_offer``."""
    if current is not OfferStatus.PENDING:
        raise InvalidOfferTransitionError(current_status=current.value, command=command.value)
    return _OFFER_DECISION[command]


def is_offer_expired(*, now: datetime, expires_at: datetime) -> bool:
    """The deadline is inclusive: at ``now == expires_at`` the offer is already expired."""
    if now.utcoffset() is None or expires_at.utcoffset() is None:
        raise ValueError("Offer deadline check needs timezone-aware datetimes")
    return now >= expires_at


def can_accept_offer(status: OfferStatus, *, now: datetime, expires_at: datetime) -> bool:
    """Pending and strictly before the deadline, even if the expiry loop has not run yet."""
    expired = is_offer_expired(now=now, expires_at=expires_at)
    return status is OfferStatus.PENDING and not expired


def is_offer_command_already_applied(current: OfferStatus, command: OfferCommand) -> bool:
    """The caller still checks that the offer is the same driver's."""
    return _OFFER_DECISION[command] is current
