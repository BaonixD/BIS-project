from fastapi import APIRouter, status

from taxi_service.modules.auth.dependencies import UserServiceDep
from taxi_service.modules.auth.schemas import RegisterRequest
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, users: UserServiceDep) -> UserResponse:
    """Create a passenger or driver account. It does not log in: call ``/auth/login``."""
    user = await users.create_user(
        username=body.username,
        password=body.password.get_secret_value(),
        role=UserRole(body.role),
    )
    return UserResponse.model_validate(user)
