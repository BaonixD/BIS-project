import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.pricing import CURRENCY


class PaymentMethodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: PaymentMethod


class PaymentResponse(BaseModel):
    """``payment_url`` is the configured Kaspi link for ``kaspi_link``, otherwise null."""

    ride_id: uuid.UUID
    amount_kzt: int
    currency: Literal["KZT"]
    method: PaymentMethod
    status: PaymentStatus
    paid_at: datetime | None
    payment_url: str | None

    @classmethod
    def build(cls, payment: Payment, settings: PaymentSettings) -> Self:
        is_kaspi = payment.method is PaymentMethod.KASPI_LINK
        return cls(
            ride_id=payment.ride_id,
            amount_kzt=payment.amount_kzt,
            currency=CURRENCY,
            method=payment.method,
            status=payment.status,
            paid_at=payment.paid_at,
            payment_url=settings.kaspi_payment_url if is_kaspi else None,
        )
