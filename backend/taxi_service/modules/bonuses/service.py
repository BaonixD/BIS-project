import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.database.session import read_transaction
from taxi_service.modules.bonuses import records
from taxi_service.modules.bonuses.schemas import BonusBalance


async def my_balance(db: AsyncSession, user_id: uuid.UUID) -> BonusBalance:
    async with read_transaction(db):
        amount = await records.balance(db, user_id)
    return BonusBalance(
        balance_kzt=amount,
        earn_percent=records.EARN_PERCENT,
        max_share_percent=records.MAX_SHARE_PERCENT,
    )
