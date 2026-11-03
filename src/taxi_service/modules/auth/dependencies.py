import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie, APIKeyHeader

from taxi_service.core.clock import ClockDep
from taxi_service.core.config import SettingsDep
from taxi_service.core.origins import normalize_origin
from taxi_service.database.session import DbSession
from taxi_service.modules.auth import service
from taxi_service.modules.auth.cookies import SESSION_COOKIE_NAME
from taxi_service.modules.auth.exceptions import (
    CsrfFailedError,
    ForbiddenError,
    NotAuthenticatedError,
    OriginNotAllowedError,
)
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.users.models import UserRole

CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

session_cookie = APIKeyCookie(
    name=SESSION_COOKIE_NAME,
    scheme_name="SessionCookie",
    description="HttpOnly session cookie set by POST /api/v1/auth/login.",
    auto_error=False,
)
csrf_header = APIKeyHeader(
    name=CSRF_HEADER_NAME,
    scheme_name="CsrfToken",
    description="csrf_token from GET /api/v1/auth/session; required on unsafe methods.",
    auto_error=False,
)


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_login_limiter(request: Request) -> LoginAttemptLimiter:
    limiter: LoginAttemptLimiter = request.app.state.login_limiter
    return limiter


LoginLimiterDep = Annotated[LoginAttemptLimiter, Depends(get_login_limiter)]


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(session_cookie)],
    csrf_token: Annotated[str | None, Depends(csrf_header)],
    db: DbSession,
    clock: ClockDep,
) -> AuthenticatedUser:
    """Unsafe methods also need the session's CSRF token: every ``CurrentUser`` route has it."""
    if not token:
        raise NotAuthenticatedError
    user = await service.authenticate(db, token, clock=clock)
    if request.method not in SAFE_METHODS and not _same_token(csrf_token, user.csrf_token):
        raise CsrfFailedError
    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[AuthenticatedUser]]:
    if not roles:
        raise ValueError("require_roles needs at least one role")
    allowed = frozenset(roles)

    async def current_user_with_role(user: CurrentUser) -> AuthenticatedUser:
        if user.role not in allowed:
            raise ForbiddenError
        return user

    return current_user_with_role


AdminUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.ADMIN))]


def require_allowed_origin(request: Request, settings: SettingsDep) -> None:
    """Login and register have no CSRF token yet; browsers send ``Origin`` cross-site."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    try:
        normalized = normalize_origin(origin)
    except ValueError:
        raise OriginNotAllowedError from None
    if normalized not in settings.cors_allowed_origins and normalized != _own_origin(request):
        raise OriginNotAllowedError


def _own_origin(request: Request) -> str | None:
    host = request.headers.get("host")
    if not host:
        return None
    try:
        return normalize_origin(f"{request.url.scheme}://{host}")
    except ValueError:
        return None


def _same_token(received: str | None, expected: str) -> bool:
    return received is not None and hmac.compare_digest(received.encode(), expected.encode())
