"""Payment of a completed ride: cash or the Kaspi link; the passenger's "Paid" counts at once."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.exceptions import (
    InvalidPaymentTransitionError,
    KaspiUnavailableError,
    PaymentActionForbiddenError,
    PaymentNotFoundError,
    RideNotCompletedError,
)
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.pricing import CURRENCY
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.transitions import lock_ride
from taxi_service.modules.users.models import UserRole

CHANGE_METHOD: Final = "change_method"
PAY: Final = "pay"


async def open_payment(db: AsyncSession, ride: Ride, now: datetime) -> Payment:
    """In the completion transaction; the unique ``ride_id`` refuses a second payment."""
    payment = Payment(
        id=uuid.uuid4(),
        ride_id=ride.id,
        amount_kzt=ride.amount_kzt,
        currency=CURRENCY,
        method=PaymentMethod.CASH,
        status=PaymentStatus.UNPAID,
        created_at=now,
        updated_at=now,
    )
    db.add(payment)
    await db.flush()
    return payment


async def get_payment(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole
) -> Payment:
    async with read_transaction(db):
        ride = _require_visible(await db.get(Ride, ride_id), user_id, role)
        _require_completed(ride)
        payment = await db.scalar(select(Payment).where(Payment.ride_id == ride_id))
    if payment is None:
        raise PaymentNotFoundError
    return payment


async def change_method(
    db: AsyncSession,
    ride_id: uuid.UUID,
    method: PaymentMethod,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    clock: Clock,
    settings: PaymentSettings,
) -> Payment:
    async with db.begin():
        payment = await _lock_for_passenger(db, ride_id, user_id, role, action=CHANGE_METHOD)
        if payment.status is PaymentStatus.PAID:
            raise InvalidPaymentTransitionError(action=CHANGE_METHOD, status=payment.status.value)
        if payment.method is not method:
            if method is PaymentMethod.KASPI_LINK and not settings.kaspi_enabled:
                raise KaspiUnavailableError
            payment.method, payment.updated_at = method, clock.now()
            await db.flush()
    return payment


async def mark_paid(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole, clock: Clock
) -> Payment:
    """Idempotent: a repeat returns the payment as it was first paid."""
    async with db.begin():
        payment = await _lock_for_passenger(db, ride_id, user_id, role, action=PAY)
        if payment.status is PaymentStatus.UNPAID:
            now = clock.now()
            payment.status, payment.paid_at, payment.updated_at = PaymentStatus.PAID, now, now
            await db.flush()
    return payment


async def _lock_for_passenger(
    db: AsyncSession, ride_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, *, action: str
) -> Payment:
    """Visibility (404), then the passenger's right (403), then completion (409)."""
    ride = _require_visible(await lock_ride(db, ride_id), user_id, role)
    if role is not UserRole.PASSENGER or ride.passenger_id != user_id:
        raise PaymentActionForbiddenError(action=action)
    _require_completed(ride)
    payment = await _lock_payment(db, ride.id)
    if payment is None:
        raise PaymentNotFoundError
    return payment


def _require_visible(ride: Ride | None, user_id: uuid.UUID, role: UserRole) -> Ride:
    if ride is None or not can_view_ride(ride, user_id, role):
        raise RideNotFoundError
    return ride


def _require_completed(ride: Ride) -> None:
    if ride.status is not RideStatus.COMPLETED:
        raise RideNotCompletedError


async def _lock_payment(db: AsyncSession, ride_id: uuid.UUID) -> Payment | None:
    """Fresh and locked; the ride is locked first (rides -> payments)."""
    result = await db.execute(
        select(Payment)
        .where(Payment.ride_id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
