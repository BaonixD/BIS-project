"""Who may report, confirm or change a ride payment (MVP_SPEC section 7)."""

import unicodedata
from dataclasses import dataclass
from typing import Final

from taxi_service.modules.payments.exceptions import (
    ConfirmationReferenceRequiredError,
    InvalidConfirmationReferenceError,
    PaymentActionForbiddenError,
    RideNotCompletedError,
)
from taxi_service.modules.payments.rules import PaymentAction, PaymentMethod
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.users.models import UserRole

MAX_CONFIRMATION_REFERENCE_LENGTH: Final = 200

# Control, format (bidi, zero-width), surrogate, private-use, unassigned; line/paragraph breaks.
_UNSAFE_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentActor:
    """The caller as seen from one ride; the service fills the flags from the ride row."""

    role: UserRole
    is_ride_passenger: bool
    is_assigned_driver: bool
    ride_completed: bool

    @property
    def is_passenger(self) -> bool:
        return self.role is UserRole.PASSENGER and self.is_ride_passenger

    @property
    def is_driver(self) -> bool:
        return self.role is UserRole.DRIVER and self.is_assigned_driver

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN


def authorize_payment_action(
    action: PaymentAction, actor: PaymentActor, *, method: PaymentMethod
) -> None:
    """Visibility (404), then role right (403), then ride completion (409)."""
    if not (actor.is_passenger or actor.is_driver or actor.is_admin):
        raise RideNotFoundError()
    if not _has_right(action, actor, method):
        raise PaymentActionForbiddenError(action=action.value)
    if not actor.ride_completed:
        raise RideNotCompletedError()


def _has_right(action: PaymentAction, actor: PaymentActor, method: PaymentMethod) -> bool:
    if action is not PaymentAction.CONFIRM:
        return actor.is_passenger
    if method is PaymentMethod.CASH:
        return actor.is_driver or actor.is_admin
    return actor.is_admin


def normalize_confirmation_reference(method: PaymentMethod, raw: str | None) -> str | None:
    """Trimmed note; required for Kaspi reconciliation, optional for cash."""
    value = (raw or "").strip()
    if not value:
        if method is PaymentMethod.KASPI_LINK:
            raise ConfirmationReferenceRequiredError()
        return None
    if len(value) > MAX_CONFIRMATION_REFERENCE_LENGTH or not _is_plain_text(value):
        raise InvalidConfirmationReferenceError(max_length=MAX_CONFIRMATION_REFERENCE_LENGTH)
    return value


def _is_plain_text(value: str) -> bool:
    return all(unicodedata.category(char) not in _UNSAFE_CATEGORIES for char in value)
