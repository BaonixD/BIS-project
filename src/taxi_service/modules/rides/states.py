from dataclasses import dataclass
from enum import StrEnum
from typing import Final

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


ACTIVE_RIDE_STATUSES: Final[frozenset[RideStatus]] = frozenset()
TERMINAL_RIDE_STATUSES: Final[frozenset[RideStatus]] = frozenset()
PRE_START_RIDE_STATUSES: Final[frozenset[RideStatus]] = frozenset()
TERMINAL_OFFER_STATUSES: Final[frozenset[OfferStatus]] = frozenset()


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


SYSTEM_ACTOR: Final = Actor(role=None)


def next_status(current: RideStatus, command: RideCommand, actor: Actor) -> RideStatus:
    return current
