from fastapi import APIRouter

from taxi_service.modules.auth.dependencies import CurrentUser, UserServiceDep
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.users.models import UserProfile
from taxi_service.modules.users.schemas import MyProfileResponse, MyProfileUpdate
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", responses=error_responses(401))
async def read_my_profile(user: CurrentUser, users: UserServiceDep) -> MyProfileResponse:
    """The caller's own account and contact details; any role."""
    return _response(user, await users.get_profile(user.id))


@router.patch("/me", responses=error_responses(401, 403))
async def update_my_profile(
    body: MyProfileUpdate, user: CurrentUser, users: UserServiceDep
) -> MyProfileResponse:
    """Change ``display_name`` and/or ``phone``. Role, username and approval are not writable."""
    return _response(user, await users.update_profile(user.id, body))


def _response(user: AuthenticatedUser, profile: UserProfile | None) -> MyProfileResponse:
    return MyProfileResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
        display_name=profile.display_name if profile else None,
        phone=profile.phone if profile else None,
    )
