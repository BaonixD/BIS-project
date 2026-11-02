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
    return PaymentInstructions(
        ride_id=ride_id,
        amount_kzt=amount_kzt,
        currency=CURRENCY,
        method=state.method,
        status=state.status,
        verification=Verification.MANUAL,
        kaspi_available=settings.kaspi_enabled,
        payment_url=settings.kaspi_payment_url,
        amount_entered_by_buyer=False,
        notice="",
    )
