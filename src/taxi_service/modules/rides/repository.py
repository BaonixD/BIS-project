import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import RideQuote


class RideRepository:
    """Data access for quotes, rides and idempotency records; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_quote(self, quote: RideQuote) -> None:
        self._session.add(quote)
        await self._session.flush()

    async def get_quote(self, quote_id: uuid.UUID) -> RideQuote | None:
        return await self._session.get(RideQuote, quote_id)
