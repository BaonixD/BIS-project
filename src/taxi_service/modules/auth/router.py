from fastapi import APIRouter, Response, status

from taxi_service.core.config import Settings, SettingsDep
from taxi_service.modules.auth.dependencies import (
    SESSION_COOKIE_NAME,
    AuthServiceDep,
    CurrentUser,
    UserServiceDep,
)
from taxi_service.modules.auth.schemas import LoginRequest, RegisterRequest, SessionResponse
from taxi_service.modules.auth.service import SESSION_TTL
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


@router.post("/login")
async def login(
    body: LoginRequest, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> SessionResponse:
    """Open a 7-day session: sets the HttpOnly session cookie and returns the CSRF token."""
    issued = await auth.login(body.username, body.password.get_secret_value())
    _set_session_cookie(response, issued.token, settings)
    return SessionResponse.from_user(issued.user)


@router.get("/session")
async def read_session(user: CurrentUser) -> SessionResponse:
    """Current user and the session's CSRF token (for the X-CSRF-Token header)."""
    return SessionResponse.from_user(user)


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
