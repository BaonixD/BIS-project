"""Payment rows written in the ride's own transactions: the order, cancel and ``no_driver``.

Kaspi is a simulated charge: ``paid`` with the order, ``refunded`` if the ride does not happen.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.pricing import CURRENCY


async def open_payment(
    db: AsyncSession, ride: Ride, method: PaymentMethod, now: datetime
) -> Payment:
    """Cash stays ``unpaid`` until the driver gets it; the unique ``ride_id`` refuses a second."""
    paid_at = now if method is PaymentMethod.KASPI_LINK else None
    payment = Payment(
        id=uuid.uuid4(),
        ride_id=ride.id,
        amount_kzt=ride.amount_kzt,
        currency=CURRENCY,
        method=method,
        status=PaymentStatus.UNPAID if paid_at is None else PaymentStatus.PAID,
        paid_at=paid_at,
        refunded_at=None,
        created_at=now,
        updated_at=now,
    )
    ride.payment = payment
    db.add(payment)
    await db.flush()
    return payment


async def refund_if_paid(db: AsyncSession, ride: Ride, now: datetime) -> None:
    """The caller has locked the ride and just ended it without a trip."""
    payment = await lock_payment(db, ride.id)
    if payment is not None and payment.status is PaymentStatus.PAID:
        payment.status, payment.refunded_at, payment.updated_at = PaymentStatus.REFUNDED, now, now
        await db.flush()


async def lock_payment(db: AsyncSession, ride_id: uuid.UUID) -> Payment | None:
    """Fresh and locked; the ride is locked first (rides -> payments)."""
    result = await db.execute(
        select(Payment)
        .where(Payment.ride_id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
