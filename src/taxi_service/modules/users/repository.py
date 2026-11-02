from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.users.models import User


def normalize_username(username: str) -> str:
    """Key of case-insensitive uniqueness and login lookup (usernames are ASCII)."""
    return username.lower()


class UserRepository:
    """Data access for ``users``; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        """Insert now, so a duplicate username raises ``IntegrityError`` here."""
        self._session.add(user)
        await self._session.flush()

    async def get_by_username(self, username: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.username_normalized == normalize_username(username))
        )
