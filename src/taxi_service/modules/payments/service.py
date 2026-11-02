"""Payment record of a ride: opened by its completion (MVP_SPEC §7, ADR 0004)."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.payments.models import Payment, PaymentEventAction
from taxi_service.modules.payments.repository import PaymentRepository
from taxi_service.modules.payments.rules import Verification, initial_payment_state
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.pricing import CURRENCY


async def open_payment(session: AsyncSession, ride: Ride, now: datetime) -> Payment:
    """Unpaid cash payment of the just completed ``ride``, with its ``open`` audit row.

    Runs in the caller's transaction and never commits; the unique ``ride_id``
    makes a second payment of the same ride fail and roll the caller back.
    """
    state = initial_payment_state()
    payment = Payment(
        id=uuid.uuid4(),
        ride_id=ride.id,
        amount_kzt=ride.amount_kzt,
        currency=CURRENCY,
        method=state.method,
        status=state.status,
        verification=Verification.MANUAL,
        created_at=now,
        updated_at=now,
    )
    payments = PaymentRepository(session)
    await payments.add(payment)
    await payments.record(payment, PaymentEventAction.OPEN, previous=None, actor_id=None, now=now)
    return payment
