import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import (
    ACCEPTED_ACTIVE_RIDE_STATUSES,
    IdempotencyRecord,
    Ride,
    RideQuote,
)
from taxi_service.modules.rides.states import ACTIVE_RIDE_STATUSES


class RideRepository:
    """Data access for quotes, rides and idempotency records; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_quote(self, quote: RideQuote) -> None:
        self._session.add(quote)
        await self._session.flush()

    async def get_quote(self, quote_id: uuid.UUID) -> RideQuote | None:
        return await self._session.get(RideQuote, quote_id)

    async def quote_is_used(self, quote_id: uuid.UUID) -> bool:
        found = await self._session.scalar(select(Ride.id).where(Ride.quote_id == quote_id))
        return found is not None

    async def add_ride(self, ride: Ride) -> None:
        self._session.add(ride)
        await self._session.flush()

    async def get_ride(self, ride_id: uuid.UUID) -> Ride | None:
        return await self._session.get(Ride, ride_id)

    async def lock_ride(self, ride_id: uuid.UUID) -> Ride | None:
        """The ride, fresh from the database and locked for the rest of the transaction.

        Lock the ride before its offers (rides -> ride_offers, ADR 0006).
        """
        result = await self._session.execute(
            select(Ride)
            .where(Ride.id == ride_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def has_active_ride(self, passenger_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(Ride.id).where(
                Ride.passenger_id == passenger_id, Ride.status.in_(ACTIVE_RIDE_STATUSES)
            )
        )
        return found is not None

    async def get_idempotency_record(
        self, user_id: uuid.UUID, operation: str, key: str
    ) -> IdempotencyRecord | None:
        return await self._session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == key,
            )
        )

    async def add_idempotency_record(self, record: IdempotencyRecord) -> None:
        self._session.add(record)
        await self._session.flush()


async def driver_has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    """Whether the driver holds an assigned, arrived or in_progress ride (caller's transaction)."""
    found = await session.scalar(
        select(Ride.id).where(
            Ride.driver_id == driver_id, Ride.status.in_(ACCEPTED_ACTIVE_RIDE_STATUSES)
        )
    )
    return found is not None
