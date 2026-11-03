"""Payment of a completed ride; manual verification only, nothing here asks Kaspi (ADR 0004)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.exceptions import PaymentNotFoundError, RideNotCompletedError
from taxi_service.modules.payments.models import Payment, PaymentEvent, PaymentEventAction
from taxi_service.modules.payments.permissions import (
    PaymentActor,
    authorize_payment_action,
    normalize_confirmation_reference,
)
from taxi_service.modules.payments.rules import (
    PaymentAction,
    PaymentDecision,
    PaymentMethod,
    PaymentState,
    PaymentStatus,
    Verification,
    apply_confirm,
    apply_method_change,
    apply_report,
    initial_payment_state,
)
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.pricing import CURRENCY
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.transitions import lock_ride
from taxi_service.modules.users.models import UserRole


@dataclass(frozen=True, slots=True)
class PaymentResult:
    """``changed`` is false for an idempotent repeat."""

    payment: Payment
    changed: bool


async def open_payment(db: AsyncSession, ride: Ride, now: datetime) -> Payment:
    """In the completion transaction; the unique ``ride_id`` refuses a second payment."""
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
    db.add(payment)
    await db.flush()
    await _record(db, payment, PaymentEventAction.OPEN, previous=None, actor_id=None, now=now)
    return payment


async def get_payment(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole
) -> Payment:
    async with read_transaction(db):
        ride = await db.get(Ride, ride_id)
        if ride is None or not can_view_ride(ride, user_id, role):
            raise RideNotFoundError
        if ride.status is not RideStatus.COMPLETED:
            raise RideNotCompletedError
        payment = await db.scalar(select(Payment).where(Payment.ride_id == ride.id))
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
) -> PaymentResult:
    kaspi_enabled = settings.kaspi_enabled

    def decide(state: PaymentState) -> PaymentDecision:
        return apply_method_change(state, method, kaspi_enabled=kaspi_enabled)

    return await _run(db, ride_id, PaymentAction.CHANGE_METHOD, user_id, role, decide, clock)


async def report_payment(
    db: AsyncSession, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole, clock: Clock
) -> PaymentResult:
    """A statement only: ``reported``, never ``confirmed``."""
    return await _run(db, ride_id, PaymentAction.REPORT, user_id, role, apply_report, clock)


async def confirm_payment(
    db: AsyncSession,
    ride_id: uuid.UUID,
    reference: str | None,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    clock: Clock,
) -> PaymentResult:
    return await _run(
        db, ride_id, PaymentAction.CONFIRM, user_id, role, apply_confirm, clock, reference
    )


def payment_actor(ride: Ride, user_id: uuid.UUID, role: UserRole) -> PaymentActor:
    return PaymentActor(
        role=role,
        is_ride_passenger=ride.passenger_id == user_id,
        is_assigned_driver=ride.driver_id == user_id,
        ride_completed=ride.status is RideStatus.COMPLETED,
    )


def state_of(payment: Payment) -> PaymentState:
    return PaymentState(payment.method, payment.status)


async def _run(
    db: AsyncSession,
    ride_id: uuid.UUID,
    action: PaymentAction,
    user_id: uuid.UUID,
    role: UserRole,
    decide: Callable[[PaymentState], PaymentDecision],
    clock: Clock,
    reference: str | None = None,
) -> PaymentResult:
    async with db.begin():
        ride = await lock_ride(db, ride_id)
        if ride is None:
            raise RideNotFoundError
        payment = await _lock_payment(db, ride.id)
        # Before completion there is no payment yet; it would open as cash.
        state = initial_payment_state() if payment is None else state_of(payment)
        authorize_payment_action(action, payment_actor(ride, user_id, role), method=state.method)
        if payment is None:
            raise PaymentNotFoundError
        note = None
        if action is PaymentAction.CONFIRM:
            note = normalize_confirmation_reference(state.method, reference)
        decision = decide(state)
        if decision.changed:
            await _apply(db, payment, action, decision.state, user_id, note, clock.now())
    return PaymentResult(payment, decision.changed)


async def _apply(
    db: AsyncSession,
    payment: Payment,
    action: PaymentAction,
    target: PaymentState,
    user_id: uuid.UUID,
    note: str | None,
    now: datetime,
) -> None:
    previous = (payment.status, payment.method)
    payment.method, payment.status, payment.updated_at = target.method, target.status, now
    if action is PaymentAction.REPORT:
        payment.reported_at = now
    elif action is PaymentAction.CHANGE_METHOD:
        payment.reported_at = None  # a Kaspi statement never carries over
    else:
        payment.confirmed_at, payment.confirmed_by = now, user_id
        payment.confirmation_reference = note
    await db.flush()
    await _record(
        db,
        payment,
        PaymentEventAction(action.value),
        previous=previous,
        actor_id=user_id,
        now=now,
        reference=note,
    )


async def _lock_payment(db: AsyncSession, ride_id: uuid.UUID) -> Payment | None:
    """Fresh and locked; the ride is locked first (rides -> payments)."""
    result = await db.execute(
        select(Payment)
        .where(Payment.ride_id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _record(
    db: AsyncSession,
    payment: Payment,
    action: PaymentEventAction,
    *,
    previous: tuple[PaymentStatus, PaymentMethod] | None,
    actor_id: uuid.UUID | None,
    now: datetime,
    reference: str | None = None,
) -> None:
    """Audit row of the change that brought ``payment`` to its current state."""
    from_status, from_method = previous if previous is not None else (None, None)
    db.add(
        PaymentEvent(
            id=uuid.uuid4(),
            payment_id=payment.id,
            action=action,
            from_status=from_status,
            to_status=payment.status,
            from_method=from_method,
            to_method=payment.method,
            actor_id=actor_id,
            reference=reference,
            created_at=now,
        )
    )
    await db.flush()
