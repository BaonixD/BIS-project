"""Payment of a ride, chosen with the order (ADR 0010); the driver confirms cash after the trip."""

import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.payments import records
from taxi_service.modules.payments.exceptions import (
    InvalidPaymentTransitionError,
    PaymentActionForbiddenError,
    PaymentNotFoundError,
    RideNotCompletedError,
)
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.transitions import lock_ride
from taxi_service.modules.users.models import UserRole

CASH_RECEIVED: Final = "cash_received"


async def get_payment(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole
) -> Payment:
    async with read_transaction(db):
        _require_visible(await db.get(Ride, ride_id), user_id, role)
        payment = await db.scalar(select(Payment).where(Payment.ride_id == ride_id))
    if payment is None:
        raise PaymentNotFoundError
    return payment


async def receive_cash(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole, clock: Clock
) -> Payment:
    """Visibility (404), the assigned driver (403), completion (409), cash (409); idempotent."""
    async with db.begin():
        ride = _require_visible(await lock_ride(db, ride_id), user_id, role)
        if role is not UserRole.DRIVER or ride.driver_id != user_id:
            raise PaymentActionForbiddenError(action=CASH_RECEIVED)
        if ride.status is not RideStatus.COMPLETED:
            raise RideNotCompletedError
        payment = await records.lock_payment(db, ride.id)
        if payment is None:
            raise PaymentNotFoundError
        if payment.method is not PaymentMethod.CASH:
            raise InvalidPaymentTransitionError(action=CASH_RECEIVED, status=payment.status.value)
        if payment.status is PaymentStatus.UNPAID:
            now = clock.now()
            payment.status, payment.paid_at, payment.updated_at = PaymentStatus.PAID, now, now
            await db.flush()
    return payment


def _require_visible(ride: Ride | None, user_id: uuid.UUID, role: UserRole) -> Ride:
    if ride is None or not can_view_ride(ride, user_id, role):
        raise RideNotFoundError
    return ride
