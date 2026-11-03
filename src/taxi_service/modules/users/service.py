import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.models import User, UserProfile, UserRole
from taxi_service.modules.users.schemas import MyProfileUpdate


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


def normalize_username(username: str) -> str:
    """Key of case-insensitive uniqueness and login lookup (usernames are ASCII)."""
    return username.lower()


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: UserRole,
    *,
    clock: Clock,
    hasher: PasswordHasher,
) -> User:
    user = User(
        username=username,
        username_normalized=normalize_username(username),
        password_hash=await hasher.hash(password),
        role=role,
        created_at=clock.now(),
    )
    try:
        async with db.begin():
            db.add(user)
            await db.flush()
    except IntegrityError as error:
        if await _username_exists(db, username):
            raise UsernameTakenError from error
        raise
    return user


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    async with read_transaction(db):
        return await _get_profile(db, user_id)


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, update: MyProfileUpdate, *, clock: Clock
) -> UserProfile:
    async with db.begin():
        profile = await _get_or_create_profile(db, user_id, clock)
        for name, value in update.changes().items():
            setattr(profile, name, value)
        profile.updated_at = clock.now()
    return profile


async def list_users(
    db: AsyncSession, role: UserRole | None, *, limit: int, offset: int
) -> UserPage:
    """Newest first (``created_at DESC, id DESC``); never the password hash."""
    conditions = _role_conditions(role)
    page = (
        select(User.id, User.username, User.role, User.created_at, UserProfile.display_name)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(*conditions)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit)
        .offset(offset)
    )
    async with read_transaction(db):
        rows = await db.execute(page)
        total = await db.scalar(select(func.count()).select_from(User).where(*conditions))
        return UserPage(rows=[UserListRow(*row) for row in rows], total=total or 0)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(
        select(User).where(User.username_normalized == normalize_username(username))
    )


async def _username_exists(db: AsyncSession, username: str) -> bool:
    async with read_transaction(db):
        return await get_user_by_username(db, username) is not None


async def _get_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    return await db.get(UserProfile, user_id)


async def _get_or_create_profile(db: AsyncSession, user_id: uuid.UUID, clock: Clock) -> UserProfile:
    """Insert the row on the first write; a concurrent first write's row wins."""
    profile = await _get_profile(db, user_id)
    if profile is not None:
        return profile
    profile = UserProfile(user_id=user_id, updated_at=clock.now())
    try:
        async with db.begin_nested():
            db.add(profile)
            await db.flush()
    except IntegrityError:
        existing = await _get_profile(db, user_id)
        if existing is None:
            raise
        return existing
    return profile


def _role_conditions(role: UserRole | None) -> list[ColumnElement[bool]]:
    return [] if role is None else [User.role == role]
