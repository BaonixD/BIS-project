"""Ratings after a completed ride, one per side (ADR 0013)."""

import uuid
from typing import Final

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.errors import violates_unique
from taxi_service.database.session import read_transaction
from taxi_service.modules.ratings import records
from taxi_service.modules.ratings.exceptions import (
    RatingAlreadyExistsError,
    RatingForbiddenError,
    RatingTagsNotAllowedError,
    RideNotCompletedError,
)
from taxi_service.modules.ratings.models import (
    ALLOWED_TAGS,
    RaterRole,
    RatingTag,
    RideRating,
    RideRatingTag,
)
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.ratings.schemas import RatingRequest
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.transitions import lock_ride
from taxi_service.modules.users.models import UserRole

ONE_PER_SIDE: Final = "uq_ride_ratings_ride_id_rater_role"


async def rate_ride(
    db: AsyncSession,
    ride_id: uuid.UUID,
    request: RatingRequest,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    clock: Clock,
) -> RideRating:
    """Checks in order: visible (404), participant (403), tags (422), completed, once (409)."""
    try:
        async with db.begin():
            ride = await lock_ride(db, ride_id)
            if ride is None or not can_view_ride(ride, user_id, role):
                raise RideNotFoundError
            rater_role = _rater_role(ride, user_id, role)
            tags = _side_tags(rater_role, request.tags)
            if ride.status is not RideStatus.COMPLETED:
                raise RideNotCompletedError
            if await records.rating_of_side(db, ride.id, rater_role) is not None:
                raise RatingAlreadyExistsError
            rating = RideRating(
                id=uuid.uuid4(),
                ride_id=ride.id,
                rater_id=user_id,
                rater_role=rater_role,
                ratee_id=_ratee(ride, rater_role),
                stars=request.stars,
                comment=request.comment,
                created_at=clock.now(),
                tag_rows=[RideRatingTag(tag=tag) for tag in tags],
            )
            db.add(rating)
            await db.flush()
    except IntegrityError as error:
        if violates_unique(error, constraint=ONE_PER_SIDE, table="ride_ratings", column="ride_id"):
            raise RatingAlreadyExistsError from error
        raise
    return rating


async def rating_of(db: AsyncSession, user_id: uuid.UUID) -> RatingSummary:
    """Average stars the user received as a driver or a passenger."""
    async with read_transaction(db):
        return await records.summary(db, user_id)


def _rater_role(ride: Ride, user_id: uuid.UUID, role: UserRole) -> RaterRole:
    if role is UserRole.PASSENGER and ride.passenger_id == user_id:
        return RaterRole.PASSENGER
    if role is UserRole.DRIVER and ride.driver_id == user_id:
        return RaterRole.DRIVER
    raise RatingForbiddenError


def _side_tags(rater_role: RaterRole, tags: list[RatingTag]) -> list[RatingTag]:
    """Unique, in the side's fixed order; a tag of the other side is a 422."""
    allowed = ALLOWED_TAGS[rater_role]
    refused = [position for position, tag in enumerate(tags) if tag not in allowed]
    if refused:
        raise RatingTagsNotAllowedError(refused, [tag.value for tag in allowed])
    return [tag for tag in allowed if tag in tags]


def _ratee(ride: Ride, rater_role: RaterRole) -> uuid.UUID:
    ratee = ride.driver_id if rater_role is RaterRole.PASSENGER else ride.passenger_id
    if ratee is None:  # a completed ride always has its driver (ck_rides_driver_matches_status)
        raise RuntimeError(f"Completed ride {ride.id} has no driver")
    return ratee
