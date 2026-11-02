from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.exceptions import NotAuthenticatedError
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.service import AuthenticatedUser, AuthService
from taxi_service.modules.users.service import UserService

SESSION_COOKIE_NAME = "taxi_session"

session_cookie = APIKeyCookie(
    name=SESSION_COOKIE_NAME,
    scheme_name="SessionCookie",
    description="HttpOnly session cookie set by POST /api/v1/auth/login. "
    "In Swagger UI log in with that endpoint; the browser then sends the cookie itself.",
    auto_error=False,
)


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_user_service(
    session: SessionDep, clock: ClockDep, hasher: PasswordHasherDep
) -> UserService:
    return UserService(session, clock, hasher)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_auth_service(
    session: SessionDep, clock: ClockDep, hasher: PasswordHasherDep
) -> AuthService:
    return AuthService(session, clock, hasher)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    token: Annotated[str | None, Depends(session_cookie)], auth: AuthServiceDep
) -> AuthenticatedUser:
    """The session's user; 401 ``not_authenticated`` without a valid session.

    The lookup runs in its own short read transaction, finished before the
    route or service begins any write transaction on the same session.
    """
    if not token:
        raise NotAuthenticatedError
    return await auth.authenticate(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
