from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from taxi_service.core.config import SettingsDep
from taxi_service.modules.auth.cookies import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    set_session_cookie,
)
from taxi_service.modules.auth.dependencies import (
    AuthServiceDep,
    CurrentUser,
    UserServiceDep,
    require_allowed_origin,
)
from taxi_service.modules.auth.schemas import LoginRequest, RegisterRequest, SessionResponse
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.schemas import UserResponse
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_allowed_origin)],
    responses=error_responses(403, 409),
)
async def register(body: RegisterRequest, users: UserServiceDep) -> UserResponse:
    """Create a passenger or driver account. It does not log in: call ``/auth/login``."""
    user = await users.create_user(
        username=body.username,
        password=body.password.get_secret_value(),
        role=UserRole(body.role),
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    dependencies=[Depends(require_allowed_origin)],
    responses=error_responses(401, 403, 429),
)
async def login(
    body: LoginRequest,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    current_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME, include_in_schema=False)
    ] = None,
) -> SessionResponse:
    """Open a 7-day session: sets the HttpOnly session cookie and returns the CSRF token.

    A session cookie the client already sends is revoked and replaced.
    """
    issued = await auth.login(
        body.username, body.password.get_secret_value(), replaces_token=current_token
    )
    set_session_cookie(response, issued.token, settings)
    return SessionResponse.from_user(issued.user)


@router.get("/session", responses=error_responses(401))
async def read_session(user: CurrentUser) -> SessionResponse:
    """Current user and the session's CSRF token (for the X-CSRF-Token header)."""
    return SessionResponse.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401, 403))
async def logout(user: CurrentUser, auth: AuthServiceDep, settings: SettingsDep) -> Response:
    """Revoke the current session and clear its cookie. Needs the X-CSRF-Token header."""
    await auth.logout(user.session_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response
