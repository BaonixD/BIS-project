"""Payment of a ride: opened by its completion, then commands of its participants.

MVP_SPEC §7, ADR 0004. Each command is one write transaction: lock the ride,
then its payment (rides -> payments), check the caller with
``authorize_payment_action`` (404, 403, then 409 before completion), decide
with the pure rules and, when something changes, update the row and write
its ``payment_events`` audit row together. A repeat changes nothing and
writes no audit row. Verification is always manual: nothing here asks Kaspi.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.exceptions import PaymentNotFoundError, RideNotCompletedError
from taxi_service.modules.payments.models import Payment, PaymentEventAction
from taxi_service.modules.payments.permissions import (
    PaymentActor,
    authorize_payment_action,
    normalize_confirmation_reference,
)
from taxi_service.modules.payments.repository import PaymentRepository
from taxi_service.modules.payments.rules import (
    PaymentAction,
    PaymentDecision,
    PaymentMethod,
    PaymentState,
    Verification,
    apply_confirm,
    apply_method_change,
    apply_report,
    initial_payment_state,
)
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.pricing import CURRENCY
from taxi_service.modules.rides.repository import RideRepository
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole


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


@dataclass(frozen=True, slots=True)
class PaymentResult:
    """The payment after a command; ``changed`` is false for an idempotent repeat."""

    payment: Payment
    changed: bool


def payment_actor(ride: Ride, user_id: uuid.UUID, role: UserRole) -> PaymentActor:
    return PaymentActor(
        role=role,
        is_ride_passenger=ride.passenger_id == user_id,
        is_assigned_driver=ride.driver_id == user_id,
        ride_completed=ride.status is RideStatus.COMPLETED,
    )


class PaymentService:
    """Payment reads and commands; callers pass the user's id and role, the service checks."""

    def __init__(self, session: AsyncSession, clock: Clock, settings: PaymentSettings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._rides = RideRepository(session)
        self._payments = PaymentRepository(session)

    async def get(self, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole) -> Payment:
        """The payment for the ride's passenger, its driver or an admin, after completion."""
        async with read_transaction(self._session):
            ride = await self._rides.get_ride(ride_id)
            if ride is None or not can_view_ride(ride, user_id, role):
                raise RideNotFoundError
            if ride.status is not RideStatus.COMPLETED:
                raise RideNotCompletedError
            payment = await self._payments.get_for_ride(ride.id)
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def change_method(
        self, ride_id: uuid.UUID, method: PaymentMethod, *, user_id: uuid.UUID, role: UserRole
    ) -> PaymentResult:
        """The passenger picks cash or Kaspi before confirmation (Kaspi only with a link)."""
        kaspi_enabled = self._settings.kaspi_enabled

        def decide(state: PaymentState) -> PaymentDecision:
            return apply_method_change(state, method, kaspi_enabled=kaspi_enabled)

        return await self._run(ride_id, PaymentAction.CHANGE_METHOD, user_id, role, decide)

    async def report(
        self, ride_id: uuid.UUID, *, user_id: uuid.UUID, role: UserRole
    ) -> PaymentResult:
        """The passenger states a Kaspi payment: ``reported``, never ``confirmed``."""
        return await self._run(ride_id, PaymentAction.REPORT, user_id, role, apply_report)

    async def confirm(
        self, ride_id: uuid.UUID, reference: str | None, *, user_id: uuid.UUID, role: UserRole
    ) -> PaymentResult:
        """Manual confirmation: cash by the driver or an admin, Kaspi by an admin with a note."""
        return await self._run(
            ride_id, PaymentAction.CONFIRM, user_id, role, apply_confirm, reference=reference
        )

    async def _run(
        self,
        ride_id: uuid.UUID,
        action: PaymentAction,
        user_id: uuid.UUID,
        role: UserRole,
        decide: Callable[[PaymentState], PaymentDecision],
        *,
        reference: str | None = None,
    ) -> PaymentResult:
        async with self._session.begin():
            ride = await self._rides.lock_ride(ride_id)
            if ride is None:
                raise RideNotFoundError
            payment = await self._payments.lock_for_ride(ride.id)
            # Before completion there is no payment yet; it would open as cash.
            state = initial_payment_state() if payment is None else state_of(payment)
            authorize_payment_action(
                action, payment_actor(ride, user_id, role), method=state.method
            )
            if payment is None:
                raise PaymentNotFoundError
            note = None
            if action is PaymentAction.CONFIRM:
                note = normalize_confirmation_reference(state.method, reference)
            decision = decide(state)
            if decision.changed:
                await self._apply(payment, action, decision.state, user_id, note)
        return PaymentResult(payment, decision.changed)

    async def _apply(
        self,
        payment: Payment,
        action: PaymentAction,
        target: PaymentState,
        user_id: uuid.UUID,
        note: str | None,
    ) -> None:
        now = self._clock.now()
        previous = (payment.status, payment.method)
        payment.method, payment.status, payment.updated_at = target.method, target.status, now
        if action is PaymentAction.REPORT:
            payment.reported_at = now
        elif action is PaymentAction.CHANGE_METHOD:
            payment.reported_at = None  # a Kaspi statement never carries over
        else:
            payment.confirmed_at, payment.confirmed_by = now, user_id
            payment.confirmation_reference = note
        await self._session.flush()
        await self._payments.record(
            payment,
            PaymentEventAction(action.value),
            previous=previous,
            actor_id=user_id,
            now=now,
            reference=note,
        )


def state_of(payment: Payment) -> PaymentState:
    return PaymentState(payment.method, payment.status)
