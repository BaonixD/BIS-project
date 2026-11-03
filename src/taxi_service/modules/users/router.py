from fastapi import APIRouter

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.ratings import service as ratings_service
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.ratings.schemas import RatingSummaryResponse
from taxi_service.modules.users import service
from taxi_service.modules.users.models import UserProfile
from taxi_service.modules.users.schemas import MyProfileResponse, MyProfileUpdate
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", responses=error_responses(401))
async def read_my_profile(user: CurrentUser, db: DbSession) -> MyProfileResponse:
    profile = await service.get_profile(db, user.id)
    return _response(user, profile, await ratings_service.rating_of(db, user.id))


@router.patch("/me", responses=error_responses(401, 403))
async def update_my_profile(
    body: MyProfileUpdate, user: CurrentUser, db: DbSession, clock: ClockDep
) -> MyProfileResponse:
    profile = await service.update_profile(db, user.id, body, clock=clock)
    return _response(user, profile, await ratings_service.rating_of(db, user.id))


def _response(
    user: AuthenticatedUser, profile: UserProfile | None, rating: RatingSummary
) -> MyProfileResponse:
    return MyProfileResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
        display_name=profile.display_name if profile else None,
        phone=profile.phone if profile else None,
        rating=RatingSummaryResponse.build(rating),
    )
