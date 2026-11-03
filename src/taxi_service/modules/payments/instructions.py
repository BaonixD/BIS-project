"""Payment instructions shown to the passenger; the future client renders the QR code."""

from dataclasses import dataclass
from uuid import UUID

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.rules import (
    PaymentMethod,
    PaymentState,
    PaymentStatus,
    Verification,
)
from taxi_service.modules.rides.pricing import CURRENCY


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentInstructions:
    ride_id: UUID
    amount_kzt: int
    currency: str
    method: PaymentMethod
    status: PaymentStatus
    verification: Verification
    kaspi_available: bool
    payment_url: str | None
    amount_entered_by_buyer: bool
    notice: str


def build_payment_instructions(
    *, ride_id: UUID, amount_kzt: int, state: PaymentState, settings: PaymentSettings
) -> PaymentInstructions:
    """``amount_kzt`` comes from the server ride snapshot; the link only from settings."""
    _require_amount(amount_kzt)
    payment_url = _payment_url(state, settings)
    return PaymentInstructions(
        ride_id=ride_id,
        amount_kzt=amount_kzt,
        currency=CURRENCY,
        method=state.method,
        status=state.status,
        verification=Verification.MANUAL,
        kaspi_available=settings.kaspi_enabled,
        payment_url=payment_url,
        amount_entered_by_buyer=payment_url is not None,
        notice=_notice(state, amount_kzt, has_link=payment_url is not None),
    )


def _require_amount(amount_kzt: int) -> None:
    # bool is an int subclass, so the exact type is checked.
    if type(amount_kzt) is not int or amount_kzt <= 0:
        raise ValueError("amount_kzt must be a positive integer")


def _payment_url(state: PaymentState, settings: PaymentSettings) -> str | None:
    if state.method is not PaymentMethod.KASPI_LINK or state.status is PaymentStatus.CONFIRMED:
        return None
    return settings.kaspi_payment_url


def _notice(state: PaymentState, amount_kzt: int, *, has_link: bool) -> str:
    if state.status is PaymentStatus.CONFIRMED:
        return "Payment was confirmed manually."
    if state.method is PaymentMethod.CASH:
        return (
            f"Pay {amount_kzt} {CURRENCY} in cash to the driver. "
            "The driver or an administrator will confirm it manually."
        )
    if not has_link:
        return (
            "Kaspi payment is not available right now. "
            "Choose cash, or wait while an administrator checks a payment you already made."
        )
    return (
        f"Open the Kaspi link or scan its QR code and enter {amount_kzt} {CURRENCY} yourself. "
        "Opening the link, scanning the QR code or reporting the payment does not confirm it; "
        "an administrator confirms it manually after checking Kaspi."
    )
