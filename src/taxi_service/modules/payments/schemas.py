import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.instructions import build_payment_instructions
from taxi_service.modules.payments.models import Payment
from taxi_service.modules.payments.rules import PaymentMethod, PaymentState, PaymentStatus
from taxi_service.modules.users.models import UserRole


class PaymentMethodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: PaymentMethod


class PaymentReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str | None = Field(
        default=None,
        description="Note of the manual check, e.g. the POS receipt number; required for "
        "Kaspi, optional for cash. Plain text up to 200 characters, no secrets.",
    )


class PaymentResponse(BaseModel):
    """``confirmed_by`` and ``confirmation_reference`` are null for everyone but admins."""

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
    def build(cls, payment: Payment, settings: PaymentSettings, *, viewer_role: UserRole) -> Self:
        return cls(**_fields(payment, settings, viewer_role=viewer_role))


class PaymentCommandResponse(PaymentResponse):
    """``changed`` is false when the command was already applied (e.g. already confirmed)."""

    changed: bool

    @classmethod
    def after(
        cls, payment: Payment, settings: PaymentSettings, *, changed: bool, viewer_role: UserRole
    ) -> Self:
        return cls(**_fields(payment, settings, viewer_role=viewer_role), changed=changed)


def _fields(
    payment: Payment, settings: PaymentSettings, *, viewer_role: UserRole
) -> dict[str, Any]:
    for_admin = viewer_role is UserRole.ADMIN
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
        "confirmed_by": payment.confirmed_by if for_admin else None,
        "confirmation_reference": payment.confirmation_reference if for_admin else None,
    }
