"""Rating reads in the caller's transaction, used by rides, drivers and users."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.ratings.models import RaterRole, RideRating

AVERAGE_DIGITS: Final = 2


@dataclass(frozen=True, slots=True)
class RatingSummary:
    average: float | None
    count: int


NO_RATINGS: Final = RatingSummary(average=None, count=0)


async def summaries(
    db: AsyncSession, user_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, RatingSummary]:
    """Ratings received by each user, one grouped query for all of them."""
    ids = set(user_ids)
    if not ids:
        return {}
    rows = await db.execute(
        select(RideRating.ratee_id, func.avg(RideRating.stars), func.count())
        .where(RideRating.ratee_id.in_(ids))
        .group_by(RideRating.ratee_id)
    )
    found = {
        ratee_id: RatingSummary(average=round(float(average), AVERAGE_DIGITS), count=count)
        for ratee_id, average, count in rows
    }
    return {user_id: found.get(user_id, NO_RATINGS) for user_id in ids}


async def summary(db: AsyncSession, user_id: uuid.UUID) -> RatingSummary:
    return (await summaries(db, [user_id]))[user_id]


async def rating_by(db: AsyncSession, ride_id: uuid.UUID, rater_id: uuid.UUID) -> RideRating | None:
    return await db.scalar(
        select(RideRating).where(RideRating.ride_id == ride_id, RideRating.rater_id == rater_id)
    )


async def rating_of_side(
    db: AsyncSession, ride_id: uuid.UUID, rater_role: RaterRole
) -> RideRating | None:
    return await db.scalar(
        select(RideRating).where(RideRating.ride_id == ride_id, RideRating.rater_role == rater_role)
    )
