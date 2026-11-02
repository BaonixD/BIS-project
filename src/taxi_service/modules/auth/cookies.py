"""The session cookie: one place for its name and attributes."""

from fastapi import Response

from taxi_service.core.config import Settings
from taxi_service.modules.auth.service import SESSION_TTL

SESSION_COOKIE_NAME = "taxi_session"


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    """HttpOnly (no script access), SameSite=Lax, Secure unless disabled for local HTTP."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
