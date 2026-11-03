import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.exceptions import InvalidCredentialsError, NotAuthenticatedError
from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import User, UserRole

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(days=7)
_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
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
    """``token`` goes into the cookie and is never stored or logged."""

    token: str = field(repr=False)
    user: AuthenticatedUser


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def login(
    db: AsyncSession,
    username: str,
    password: str,
    *,
    clock: Clock,
    hasher: PasswordHasher,
    limiter: LoginAttemptLimiter,
    replaces_token: str | None = None,
) -> IssuedSession:
    """Argon2 runs outside any transaction; ``replaces_token`` is revoked with the insert."""
    limiter_key = users_service.normalize_username(username)
    limiter.acquire(limiter_key)
    async with read_transaction(db):
        user = await users_service.get_user_by_username(db, username)
    verified = await hasher.verify(user.password_hash if user else None, password)
    if user is None or not verified:
        logger.info("Login failed")
        raise InvalidCredentialsError
    limiter.reset(limiter_key)
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = clock.now()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(_TOKEN_BYTES),
        created_at=now,
        expires_at=now + SESSION_TTL,
    )
    async with db.begin():
        if replaces_token:
            await _revoke_by_token_hash(db, hash_token(replaces_token), now)
        db.add(auth_session)
        await db.flush()
    logger.info("Login succeeded")
    return IssuedSession(token=token, user=AuthenticatedUser.from_rows(user, auth_session))


async def authenticate(db: AsyncSession, token: str, *, clock: Clock) -> AuthenticatedUser:
    async with read_transaction(db):
        found = await _get_active_session(db, hash_token(token), clock.now())
    if found is None:
        raise NotAuthenticatedError
    auth_session, user = found
    return AuthenticatedUser.from_rows(user, auth_session)


async def logout(db: AsyncSession, session_id: uuid.UUID, *, clock: Clock) -> None:
    async with db.begin():
        await _revoke(db, session_id, clock.now())
    logger.info("Logged out")


async def _get_active_session(
    db: AsyncSession, token_hash: str, now: datetime
) -> tuple[AuthSession, User] | None:
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
    ).one_or_none()
    return None if row is None else (row[0], row[1])


async def _revoke_by_token_hash(db: AsyncSession, token_hash: str, now: datetime) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def _revoke(db: AsyncSession, session_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
