import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.exceptions import InvalidCredentialsError, NotAuthenticatedError
from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter
from taxi_service.modules.auth.repository import AuthSessionRepository
from taxi_service.modules.users.models import User, UserRole
from taxi_service.modules.users.repository import UserRepository, normalize_username

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(days=7)
_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The user behind a valid session, detached from the database session."""

    id: uuid.UUID
    username: str
    role: UserRole
    created_at: datetime
    session_id: uuid.UUID
    csrf_token: str = field(repr=False)
    session_expires_at: datetime

    @classmethod
    def from_rows(cls, user: User, auth_session: AuthSession) -> "AuthenticatedUser":
        return cls(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
            session_id=auth_session.id,
            csrf_token=auth_session.csrf_token,
            session_expires_at=auth_session.expires_at,
        )


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """A new session; ``token`` goes into the cookie and is never stored or logged."""

    token: str = field(repr=False)
    user: AuthenticatedUser


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        clock: Clock,
        hasher: PasswordHasher,
        limiter: LoginAttemptLimiter,
    ) -> None:
        self._session = session
        self._clock = clock
        self._hasher = hasher
        self._limiter = limiter
        self._users = UserRepository(session)
        self._sessions = AuthSessionRepository(session)

    async def login(
        self, username: str, password: str, *, replaces_token: str | None = None
    ) -> IssuedSession:
        """Check the credentials and open a session valid for ``SESSION_TTL``.

        ``replaces_token`` is the session cookie the client already had; that
        session is revoked in the same transaction, so a browser never keeps
        two working sessions (or the previous user's one) after a login.

        The Argon2 check runs outside any transaction, so the SQLite write lock
        is held only for the INSERT. An unknown username costs the same check
        and gets the same ``InvalidCredentialsError`` as a wrong password.
        Every attempt counts against the username's limit (429 once used up);
        a successful login resets it.
        """
        limiter_key = normalize_username(username)
        self._limiter.acquire(limiter_key)
        async with read_transaction(self._session):
            user = await self._users.get_by_username(username)
        verified = await self._hasher.verify(user.password_hash if user else None, password)
        if user is None or not verified:
            logger.info("Login failed")
            raise InvalidCredentialsError
        self._limiter.reset(limiter_key)
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        now = self._clock.now()
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=secrets.token_urlsafe(_TOKEN_BYTES),
            created_at=now,
            expires_at=now + SESSION_TTL,
        )
        async with self._session.begin():
            if replaces_token:
                await self._sessions.revoke_by_token_hash(hash_token(replaces_token), now)
            await self._sessions.add(auth_session)
        logger.info("Login succeeded")
        return IssuedSession(token=token, user=AuthenticatedUser.from_rows(user, auth_session))

    async def authenticate(self, token: str) -> AuthenticatedUser:
        """The user of a valid (not revoked, not expired) session, else 401."""
        async with read_transaction(self._session):
            found = await self._sessions.get_active(hash_token(token), self._clock.now())
        if found is None:
            raise NotAuthenticatedError
        auth_session, user = found
        return AuthenticatedUser.from_rows(user, auth_session)

    async def logout(self, session_id: uuid.UUID) -> None:
        """Revoke the session; its cookie and CSRF token stop working at once."""
        async with self._session.begin():
            await self._sessions.revoke(session_id, self._clock.now())
        logger.info("Logged out")
