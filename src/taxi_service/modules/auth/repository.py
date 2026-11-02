import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.users.models import User


class AuthSessionRepository:
    """Data access for ``auth_sessions``; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, auth_session: AuthSession) -> None:
        self._session.add(auth_session)
        await self._session.flush()

    async def get_active(self, token_hash: str, now: datetime) -> tuple[AuthSession, User] | None:
        """The session with this token hash and its user, if not revoked or expired."""
        row = (
            await self._session.execute(
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

    async def revoke(self, session_id: uuid.UUID, now: datetime) -> bool:
        """Mark the session revoked; ``False`` if it already was."""
        result = await self._session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
            .returning(AuthSession.id)
        )
        return result.scalar_one_or_none() is not None
