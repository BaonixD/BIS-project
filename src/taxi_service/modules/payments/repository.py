import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.payments.models import Payment, PaymentEvent, PaymentEventAction
from taxi_service.modules.payments.rules import PaymentMethod, PaymentStatus


class PaymentRepository:
    """Payments and their audit rows; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_ride(self, ride_id: uuid.UUID) -> Payment | None:
        return await self._session.scalar(select(Payment).where(Payment.ride_id == ride_id))

    async def lock_for_ride(self, ride_id: uuid.UUID) -> Payment | None:
        """The ride's payment, fresh and locked; lock the ride first (rides -> payments)."""
        result = await self._session.execute(
            select(Payment)
            .where(Payment.ride_id == ride_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def add(self, payment: Payment) -> None:
        self._session.add(payment)
        await self._session.flush()

    async def record(
        self,
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
        self._session.add(
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
        await self._session.flush()
