import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie, APIKeyHeader

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.exceptions import CsrfFailedError, NotAuthenticatedError
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.service import AuthenticatedUser, AuthService
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.service import UserService

SESSION_COOKIE_NAME = "taxi_session"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

session_cookie = APIKeyCookie(
    name=SESSION_COOKIE_NAME,
    scheme_name="SessionCookie",
    description="HttpOnly session cookie set by POST /api/v1/auth/login. "
    "In Swagger UI log in with that endpoint; the browser then sends the cookie itself.",
    auto_error=False,
)
csrf_header = APIKeyHeader(
    name=CSRF_HEADER_NAME,
    scheme_name="CsrfToken",
    description="csrf_token from GET /api/v1/auth/session (or the login response). "
    "Required on POST/PUT/PATCH/DELETE made with the session cookie.",
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
    request: Request,
    token: Annotated[str | None, Depends(session_cookie)],
    csrf_token: Annotated[str | None, Depends(csrf_header)],
    auth: AuthServiceDep,
) -> AuthenticatedUser:
    """The session's user; 401 ``not_authenticated`` without a valid session.

    Every state-changing method also needs the session's own CSRF token in
    ``X-CSRF-Token`` (403 ``csrf_failed``), so routes using ``CurrentUser``
    are protected without extra code. The lookup runs in its own short read
    transaction, finished before the route or service begins a write.
    """
    if not token:
        raise NotAuthenticatedError
    user = await auth.authenticate(token)
    if request.method not in SAFE_METHODS and not _same_token(csrf_token, user.csrf_token):
        raise CsrfFailedError
    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[AuthenticatedUser]]:
    async def current_user_with_role(user: CurrentUser) -> AuthenticatedUser:
        return user

    return current_user_with_role


def _same_token(received: str | None, expected: str) -> bool:
    return received is not None and hmac.compare_digest(received.encode(), expected.encode())
