"""Bonus moves inside a ride's own transaction (order, upgrade, completion, cancel, no driver).

A ride earns ``EARN_PERCENT`` of the money paid; bonuses cover at most half of its price, so
the payment always keeps a positive amount.
"""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.bonuses.models import BonusEntry, BonusKind, BonusWallet
from taxi_service.modules.rides.models import Ride

EARN_PERCENT: Final = 5
MAX_SHARE_PERCENT: Final = 50


def bonus_limit(amount_kzt: int) -> int:
    """The most bonuses a ride of this price may use."""
    return amount_kzt * MAX_SHARE_PERCENT // 100


async def balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    value = await db.scalar(select(BonusWallet.balance_kzt).where(BonusWallet.user_id == user_id))
    return value or 0


async def spend_on(db: AsyncSession, ride: Ride, now: datetime) -> int:
    """Use as many bonuses as the ride's limit and the balance allow; returns the amount."""
    wanted = min(
        bonus_limit(ride.amount_kzt) - ride.bonus_kzt, await balance(db, ride.passenger_id)
    )
    if wanted <= 0:
        return 0
    result = await db.execute(
        update(BonusWallet)
        .where(BonusWallet.user_id == ride.passenger_id, BonusWallet.balance_kzt >= wanted)
        .values(balance_kzt=BonusWallet.balance_kzt - wanted, updated_at=now)
    )
    if not isinstance(result, CursorResult) or result.rowcount != 1:
        return 0
    ride.bonus_kzt += wanted
    db.add(_entry(ride, BonusKind.SPEND, wanted, now))
    await db.flush()
    return wanted


async def earn_for(db: AsyncSession, ride: Ride, now: datetime) -> None:
    """The caller completed the ride; bonuses come from the money part of its price."""
    amount = (ride.amount_kzt - ride.bonus_kzt) * EARN_PERCENT // 100
    if amount > 0:
        await _credit(db, ride, BonusKind.EARN, amount, now)


async def return_spent(db: AsyncSession, ride: Ride, now: datetime) -> None:
    """The caller ended the ride without a trip (cancel or no driver)."""
    if ride.bonus_kzt > 0:
        await _credit(db, ride, BonusKind.RETURN, ride.bonus_kzt, now)


async def _credit(
    db: AsyncSession, ride: Ride, kind: BonusKind, amount: int, now: datetime
) -> None:
    result = await db.execute(
        update(BonusWallet)
        .where(BonusWallet.user_id == ride.passenger_id)
        .values(balance_kzt=BonusWallet.balance_kzt + amount, updated_at=now)
    )
    if not isinstance(result, CursorResult) or result.rowcount == 0:
        db.add(BonusWallet(user_id=ride.passenger_id, balance_kzt=amount, updated_at=now))
    db.add(_entry(ride, kind, amount, now))
    await db.flush()


def _entry(ride: Ride, kind: BonusKind, amount: int, now: datetime) -> BonusEntry:
    return BonusEntry(
        id=uuid.uuid4(),
        user_id=ride.passenger_id,
        ride_id=ride.id,
        kind=kind,
        amount_kzt=amount,
        created_at=now,
    )
