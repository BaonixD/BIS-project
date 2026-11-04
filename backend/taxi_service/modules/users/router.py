from fastapi import APIRouter

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.users import service
from taxi_service.modules.users.schemas import MyProfileResponse, MyProfileUpdate
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", responses=error_responses(401))
async def read_my_profile(user: CurrentUser, db: DbSession) -> MyProfileResponse:
    mine = await service.get_my_profile(db, user.id)
    return MyProfileResponse.build(mine.user, mine.profile, mine.rating)


@router.patch("/me", responses=error_responses(401, 403))
async def update_my_profile(
    body: MyProfileUpdate, user: CurrentUser, db: DbSession, clock: ClockDep
) -> MyProfileResponse:
    mine = await service.update_my_profile(db, user.id, body, clock=clock)
    return MyProfileResponse.build(mine.user, mine.profile, mine.rating)
