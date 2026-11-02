"""Who may report, confirm or change a ride payment (MVP_SPEC section 7)."""

from dataclasses import dataclass
from typing import Final

from taxi_service.modules.payments.rules import PaymentAction, PaymentMethod
from taxi_service.modules.users.models import UserRole

MAX_CONFIRMATION_REFERENCE_LENGTH: Final = 200


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentActor:
    """The caller as seen from one ride; the service fills the flags from the ride row."""

    role: UserRole
    is_ride_passenger: bool
    is_assigned_driver: bool
    ride_completed: bool


def authorize_payment_action(
    action: PaymentAction, actor: PaymentActor, *, method: PaymentMethod
) -> None:
    return None


def normalize_confirmation_reference(method: PaymentMethod, raw: str | None) -> str | None:
    return raw
