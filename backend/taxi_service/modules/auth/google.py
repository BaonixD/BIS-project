import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from google.auth import exceptions as google_errors
from google.auth import transport
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from taxi_service.modules.auth.exceptions import (
    GoogleLoginUnavailableError,
    InvalidGoogleTokenError,
)

CERTS_TIMEOUT_S = 5.0
CLOCK_SKEW_S = 10


@dataclass(frozen=True, slots=True)
class GoogleClaims:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None

    @classmethod
    def from_token(cls, claims: Mapping[str, Any]) -> "GoogleClaims":
        sub, email, name = claims.get("sub"), claims.get("email"), claims.get("name")
        if not isinstance(sub, str) or not sub:
            raise InvalidGoogleTokenError
        return cls(
            sub=sub,
            email=email if isinstance(email, str) and email else None,
            email_verified=claims.get("email_verified") is True,
            name=name if isinstance(name, str) else None,
        )


class GoogleTokenVerifier(Protocol):
    async def verify(self, credential: str, *, audience: str) -> GoogleClaims: ...


class _TimedRequest(google_requests.Request):
    """google-auth fetches Google's certificates with a 120 s default timeout."""

    def __call__(self, *args: Any, **kwargs: Any) -> transport.Response:
        kwargs["timeout"] = CERTS_TIMEOUT_S
        response: transport.Response = super().__call__(*args, **kwargs)  # type: ignore[no-untyped-call]
        return response


class GoogleIdTokenVerifier:
    """google-auth's ``verify_oauth2_token``: signature, issuer, audience and expiry.

    Each call fetches Google's certificates, so it runs in a worker thread.
    """

    def __init__(self, request: transport.Request | None = None) -> None:
        self._request = request or _TimedRequest()

    async def verify(self, credential: str, *, audience: str) -> GoogleClaims:
        return await asyncio.to_thread(self._verify, credential, audience)

    def _verify(self, credential: str, audience: str) -> GoogleClaims:
        try:
            claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                credential, self._request, audience=audience, clock_skew_in_seconds=CLOCK_SKEW_S
            )
        except google_errors.TransportError as error:
            raise GoogleLoginUnavailableError from error
        except (ValueError, KeyError, google_errors.GoogleAuthError) as error:
            raise InvalidGoogleTokenError from error
        return GoogleClaims.from_token(claims)
