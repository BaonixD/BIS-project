import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.database.session import read_transaction
from taxi_service.modules.ratings.models import RideRating
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole


class Achievement(BaseModel):
    code: str
    current: float
    target: float
    unlocked: bool
    sample_count: int | None = None
    minimum_samples: int | None = None


class Progress(BaseModel):
    completed_rides: int
    achievements: list[Achievement]


async def progress(db: AsyncSession, user_id: uuid.UUID, role: UserRole) -> Progress:
    if role is UserRole.ADMIN:
        return Progress(completed_rides=0, achievements=[])
    async with read_transaction(db):
        owner = Ride.driver_id if role is UserRole.DRIVER else Ride.passenger_id
        completed = (
            await db.scalar(
                select(func.count())
                .select_from(Ride)
                .where(owner == user_id, Ride.status == RideStatus.COMPLETED)
            )
            or 0
        )
        goals: list[Achievement]
        if role is UserRole.PASSENGER:
            rated = (
                await db.scalar(
                    select(func.count())
                    .select_from(RideRating)
                    .join(Ride, Ride.id == RideRating.ride_id)
                    .where(RideRating.rater_id == user_id, Ride.status == RideStatus.COMPLETED)
                )
                or 0
            )
            goals = [
                Achievement(
                    code="first_ride", current=completed, target=1, unlocked=completed >= 1
                ),
                Achievement(
                    code="regular_passenger", current=completed, target=5, unlocked=completed >= 5
                ),
                Achievement(code="feedback", current=rated, target=3, unlocked=rated >= 3),
            ]
        else:
            count, total = (
                await db.execute(
                    select(func.count(), func.coalesce(func.sum(RideRating.stars), 0)).where(
                        RideRating.ratee_id == user_id
                    )
                )
            ).one()
            average = total / count if count else 0
            goals = [
                Achievement(
                    code="first_order", current=completed, target=1, unlocked=completed >= 1
                ),
                Achievement(
                    code="experienced_driver",
                    current=completed,
                    target=10,
                    unlocked=completed >= 10,
                ),
                Achievement(
                    code="high_rating",
                    current=average,
                    target=4.8,
                    unlocked=count >= 5 and total * 10 >= count * 48,
                    sample_count=count,
                    minimum_samples=5,
                ),
            ]
    return Progress(completed_rides=completed, achievements=goals)
