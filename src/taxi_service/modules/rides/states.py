from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from taxi_service.modules.rides.exceptions import InvalidRideTransitionError
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

    @property
    def is_system(self) -> bool:
        return False


SYSTEM_ACTOR: Final = Actor(role=None)


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
    target = _TRANSITIONS[command].get(current)
    if target is None:
        raise InvalidRideTransitionError(current_status=current.value, command=command.value)
    return target
