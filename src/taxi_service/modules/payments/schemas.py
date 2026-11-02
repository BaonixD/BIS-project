"""Payment API bodies. Requests are closed (extra fields are 422): amount, link and status
always come from the server."""

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.instructions import build_payment_instructions
from taxi_service.modules.payments.models import Payment
from taxi_service.modules.payments.rules import PaymentMethod, PaymentState, PaymentStatus


class PaymentMethodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: PaymentMethod


class PaymentReportRequest(BaseModel):
    """Optional empty body of ``report``: the statement carries no amount or proof."""

    model_config = ConfigDict(extra="forbid")


class PaymentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str | None = Field(
        default=None,
        description="Note of the manual check, e.g. the POS receipt number; required for "
        "Kaspi, optional for cash. Plain text up to 200 characters, no secrets.",
    )


class PaymentResponse(BaseModel):
    """What to pay and the payment's state; ``verification`` is always ``manual``.

    ``payment_url`` is the configured Kaspi link, only for ``kaspi_link``
    before confirmation; the buyer types the amount in Kaspi. The client may
    show it as a QR code. ``confirmation_reference`` is shown to admins only.
    """

    ride_id: uuid.UUID
    amount_kzt: int
    currency: Literal["KZT"]
    method: PaymentMethod
    status: PaymentStatus
    verification: Literal["manual"]
    kaspi_available: bool
    payment_url: str | None
    amount_entered_by_buyer: bool
    notice: str
    reported_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by: uuid.UUID | None
    confirmation_reference: str | None

    @classmethod
    def build(cls, payment: Payment, settings: PaymentSettings, *, show_reference: bool) -> Self:
        return cls(**_fields(payment, settings, show_reference=show_reference))


class PaymentCommandResponse(PaymentResponse):
    """``changed`` is false when the command was already applied (e.g. already confirmed)."""

    changed: bool

    @classmethod
    def after(
        cls, payment: Payment, settings: PaymentSettings, *, changed: bool, show_reference: bool
    ) -> Self:
        return cls(**_fields(payment, settings, show_reference=show_reference), changed=changed)


def _fields(payment: Payment, settings: PaymentSettings, *, show_reference: bool) -> dict[str, Any]:
    instructions = build_payment_instructions(
        ride_id=payment.ride_id,
        amount_kzt=payment.amount_kzt,
        state=PaymentState(payment.method, payment.status),
        settings=settings,
    )
    return {
        "ride_id": instructions.ride_id,
        "amount_kzt": instructions.amount_kzt,
        "currency": instructions.currency,
        "method": instructions.method,
        "status": instructions.status,
        "verification": instructions.verification.value,
        "kaspi_available": instructions.kaspi_available,
        "payment_url": instructions.payment_url,
        "amount_entered_by_buyer": instructions.amount_entered_by_buyer,
        "notice": instructions.notice,
        "reported_at": payment.reported_at,
        "confirmed_at": payment.confirmed_at,
        "confirmed_by": payment.confirmed_by,
        "confirmation_reference": payment.confirmation_reference if show_reference else None,
    }
