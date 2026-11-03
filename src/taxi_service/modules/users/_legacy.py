"""Temporary adapters over users.service for callers not yet moved to its functions."""

# users.service re-exports UserService from here, so its functions are imported on use.

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.models import User, UserProfile, UserRole
from taxi_service.modules.users.schemas import MyProfileUpdate


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        from taxi_service.modules.users.service import get_user_by_username

        return await get_user_by_username(self._session, username)

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile | None:
        return await self._session.get(UserProfile, user_id)


class UserService:
    def __init__(self, session: AsyncSession, clock: Clock, hasher: PasswordHasher) -> None:
        self._session = session
        self._clock = clock
        self._hasher = hasher

    async def create_user(self, *, username: str, password: str, role: UserRole) -> User:
        from taxi_service.modules.users.service import create_user

        return await create_user(
            self._session, username, password, role, clock=self._clock, hasher=self._hasher
        )

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile | None:
        from taxi_service.modules.users.service import get_profile

        return await get_profile(self._session, user_id)

    async def update_profile(self, user_id: uuid.UUID, update: MyProfileUpdate) -> UserProfile:
        from taxi_service.modules.users.service import update_profile

        return await update_profile(self._session, user_id, update, clock=self._clock)
