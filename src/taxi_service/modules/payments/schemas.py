import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.pricing import CURRENCY


class PaymentResponse(BaseModel):
    """``payment_url`` is the configured Kaspi link for ``kaspi_link``, otherwise null.

    ``paid`` never proves that money arrived: Kaspi is a simulated charge (ADR 0010).
    """

    ride_id: uuid.UUID
    amount_kzt: int
    currency: Literal["KZT"]
    method: PaymentMethod
    status: PaymentStatus
    paid_at: datetime | None
    refunded_at: datetime | None
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
            refunded_at=payment.refunded_at,
            payment_url=settings.kaspi_payment_url if is_kaspi else None,
        )
