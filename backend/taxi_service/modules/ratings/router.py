import uuid

from fastapi import APIRouter, status

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.ratings import service
from taxi_service.modules.ratings.schemas import RatingRequest, RatingResponse
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides/{ride_id}/rating", tags=["ratings"])


@router.post("", status_code=status.HTTP_201_CREATED, responses=error_responses(401, 403, 404, 409))
async def rate_ride(
    ride_id: uuid.UUID, body: RatingRequest, user: CurrentUser, db: DbSession, clock: ClockDep
) -> RatingResponse:
    rating = await service.rate_ride(
        db, ride_id, body, user_id=user.id, role=user.role, clock=clock
    )
    return RatingResponse.build(rating)
