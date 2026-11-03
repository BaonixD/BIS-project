from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from taxi_service.core.clock import ClockDep
from taxi_service.core.config import SettingsDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth import service
from taxi_service.modules.auth.cookies import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    set_session_cookie,
)
from taxi_service.modules.auth.dependencies import (
    CurrentUser,
    LoginLimiterDep,
    PasswordHasherDep,
    require_allowed_origin,
)
from taxi_service.modules.auth.schemas import LoginRequest, RegisterRequest, SessionResponse
from taxi_service.modules.users import service as users_service
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
async def register(
    body: RegisterRequest, db: DbSession, clock: ClockDep, hasher: PasswordHasherDep
) -> UserResponse:
    user = await users_service.create_user(
        db,
        body.username,
        body.password.get_secret_value(),
        UserRole(body.role),
        clock=clock,
        hasher=hasher,
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
    db: DbSession,
    clock: ClockDep,
    hasher: PasswordHasherDep,
    limiter: LoginLimiterDep,
    settings: SettingsDep,
    current_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME, include_in_schema=False)
    ] = None,
) -> SessionResponse:
    issued = await service.login(
        db,
        body.username,
        body.password.get_secret_value(),
        clock=clock,
        hasher=hasher,
        limiter=limiter,
        replaces_token=current_token,
    )
    set_session_cookie(response, issued.token, settings)
    return SessionResponse.from_user(issued.user)


@router.get("/session", responses=error_responses(401))
async def read_session(user: CurrentUser) -> SessionResponse:
    return SessionResponse.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401, 403))
async def logout(
    user: CurrentUser, db: DbSession, clock: ClockDep, settings: SettingsDep
) -> Response:
    await service.logout(db, user.session_id, clock=clock)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response
