"""Read side of accounts for the admin list: allowed columns only, never the password hash."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.database.session import read_transaction
from taxi_service.modules.users.models import User, UserProfile, UserRole


@dataclass(frozen=True, slots=True)
class UserListRow:
    id: uuid.UUID
    username: str
    role: UserRole
    created_at: datetime
    display_name: str | None


@dataclass(frozen=True, slots=True)
class UserPage:
    rows: Sequence[UserListRow]
    total: int


class UserQueries:
    """Accounts newest first (``created_at DESC, id DESC``) with the profile's display name."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_users(self, role: UserRole | None, *, limit: int, offset: int) -> UserPage:
        conditions = _conditions(role)
        page = (
            select(User.id, User.username, User.role, User.created_at, UserProfile.display_name)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(*conditions)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit)
            .offset(offset)
        )
        async with read_transaction(self._session):
            rows = await self._session.execute(page)
            total = await self._session.scalar(
                select(func.count()).select_from(User).where(*conditions)
            )
            return UserPage(rows=[UserListRow(*row) for row in rows], total=total or 0)


def _conditions(role: UserRole | None) -> list[ColumnElement[bool]]:
    return [] if role is None else [User.role == role]
