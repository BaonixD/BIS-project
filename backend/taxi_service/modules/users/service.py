import re
import secrets
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.ratings import records as rating_records
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.models import (
    DISPLAY_NAME_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    User,
    UserProfile,
    UserRole,
)
from taxi_service.modules.users.schemas import MyProfileUpdate

_USERNAME_MIN_LENGTH = 3
_NOT_USERNAME_CHARACTERS = re.compile(r"[^a-z0-9_]+")
_NUMBERED_CANDIDATES = 19
_GOOGLE_CREATE_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class UserListRow:
    id: uuid.UUID
    username: str
    role: UserRole
    created_at: datetime
    display_name: str | None


@dataclass(frozen=True, slots=True)
class MyProfile:
    user: User
    profile: UserProfile | None
    rating: RatingSummary


@dataclass(frozen=True, slots=True)
class UserPage:
    rows: Sequence[UserListRow]
    total: int


def normalize_username(username: str) -> str:
    """Key of case-insensitive uniqueness and login lookup (usernames are ASCII)."""
    return username.lower()


def google_username(email: str) -> str:
    """The email's local part in username form: ``Alice.Smith@gmail.com`` -> ``alice_smith``."""
    local = email.rpartition("@")[0] or email
    base = _NOT_USERNAME_CHARACTERS.sub("_", local.lower()).strip("_")[:USERNAME_MAX_LENGTH]
    if len(base) < _USERNAME_MIN_LENGTH:
        base = f"{base}_user".lstrip("_")
    return base


def username_candidates(base: str) -> list[str]:
    """``base``, then ``base_2`` ... ``base_20``, each within the username length limit."""
    return [base] + [
        _with_suffix(base, f"_{number}") for number in range(2, _NUMBERED_CANDIDATES + 2)
    ]


async def get_or_create_google_passenger(
    db: AsyncSession,
    google_sub: str,
    email: str,
    name: str | None,
    *,
    clock: Clock,
) -> User:
    """Found by ``google_sub`` only: a matching email never links an existing account."""
    for _ in range(_GOOGLE_CREATE_ATTEMPTS - 1):
        # A concurrent first sign-in or a username taken meanwhile: look again.
        with suppress(IntegrityError):
            return await _find_or_insert_google_passenger(db, google_sub, email, name, clock)
    return await _find_or_insert_google_passenger(db, google_sub, email, name, clock)


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


async def get_my_profile(db: AsyncSession, user_id: uuid.UUID) -> MyProfile:
    """The account, its profile and the rating it received, for ``/users/me``."""
    async with read_transaction(db):
        user = await db.get_one(User, user_id)
        profile = await _get_profile(db, user_id)
        rating = await rating_records.summary(db, user_id)
    return MyProfile(user, profile, rating)


async def update_my_profile(
    db: AsyncSession, user_id: uuid.UUID, update: MyProfileUpdate, *, clock: Clock
) -> MyProfile:
    await update_profile(db, user_id, update, clock=clock)
    return await get_my_profile(db, user_id)


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


async def _find_or_insert_google_passenger(
    db: AsyncSession, google_sub: str, email: str, name: str | None, clock: Clock
) -> User:
    async with db.begin():
        existing = await db.scalar(select(User).where(User.google_sub == google_sub))
        if existing is not None:
            return existing
        username = await _free_username(db, google_username(email))
        now = clock.now()
        user = User(
            username=username,
            username_normalized=normalize_username(username),
            password_hash=None,
            google_sub=google_sub,
            email=email,
            role=UserRole.PASSENGER,
            created_at=now,
        )
        db.add(user)
        await db.flush()
        display_name = _display_name(name)
        if display_name is not None:
            db.add(UserProfile(user_id=user.id, display_name=display_name, updated_at=now))
            await db.flush()
    return user


async def _free_username(db: AsyncSession, base: str) -> str:
    candidates = username_candidates(base)
    taken = set(
        await db.scalars(
            select(User.username_normalized).where(User.username_normalized.in_(candidates))
        )
    )
    free = next((name for name in candidates if name not in taken), None)
    return free or _with_suffix(base, f"_{secrets.token_hex(4)}")


def _with_suffix(base: str, suffix: str) -> str:
    return f"{base[: USERNAME_MAX_LENGTH - len(suffix)]}{suffix}"


def _display_name(name: str | None) -> str | None:
    return (name or "").strip()[:DISPLAY_NAME_MAX_LENGTH].strip() or None
