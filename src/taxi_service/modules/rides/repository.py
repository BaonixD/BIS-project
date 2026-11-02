import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import IdempotencyRecord, RideQuote


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
        raise NotImplementedError

    async def has_active_ride(self, passenger_id: uuid.UUID) -> bool:
        raise NotImplementedError

    async def get_idempotency_record(
        self, user_id: uuid.UUID, operation: str, key: str
    ) -> IdempotencyRecord | None:
        raise NotImplementedError
