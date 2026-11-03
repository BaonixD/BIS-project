"""Account and profile writes when the constraint, not the Python pre-check, decides."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import func, select

from support.clock import ManualClock
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.models import User, UserProfile, UserRole
from taxi_service.modules.users.schemas import MyProfileUpdate

PASSWORD = "correct-horse-battery"


def missing_once(original: Callable[..., Any]) -> Callable[..., Any]:
    """The first call reports "no row yet", as a concurrent transaction would see it."""
    calls = 0

    async def lookup(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return await original(*args, **kwargs)

    return lookup


@pytest.fixture
def hasher(settings: Settings) -> PasswordHasher:
    return PasswordHasher.from_settings(settings)


async def create_user(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher, username: str
) -> User:
    async with session_factory() as db:
        return await users_service.create_user(
            db, username, PASSWORD, UserRole.PASSENGER, clock=clock, hasher=hasher
        )


async def profile_count(session_factory: SessionFactory) -> int:
    async with session_factory() as db, read_transaction(db):
        return await db.scalar(select(func.count()).select_from(UserProfile)) or 0


async def test_duplicate_username_in_other_case_is_taken(
    session_factory: SessionFactory, clock: ManualClock, hasher: PasswordHasher
) -> None:
    await create_user(session_factory, clock, hasher, "alice")

    with pytest.raises(UsernameTakenError):
        await create_user(session_factory, clock, hasher, "ALICE")

    async with session_factory() as db, read_transaction(db):
        found = await users_service.get_user_by_username(db, "Alice")
    assert found is not None
    assert found.username == "alice"


async def test_concurrent_first_profile_write_uses_the_existing_row(
    session_factory: SessionFactory,
    clock: ManualClock,
    hasher: PasswordHasher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await create_user(session_factory, clock, hasher, "root")
    async with session_factory() as db:
        await users_service.update_profile(
            db, user.id, MyProfileUpdate(display_name="Root"), clock=clock
        )
    monkeypatch.setattr(users_service, "_get_profile", missing_once(users_service._get_profile))

    async with session_factory() as db:
        profile = await users_service.update_profile(
            db, user.id, MyProfileUpdate(phone="+77011234567"), clock=clock
        )

    assert (profile.display_name, profile.phone) == ("Root", "+77011234567")
    assert await profile_count(session_factory) == 1


async def test_first_profile_write_for_a_missing_user_still_fails(
    session_factory: SessionFactory, clock: ManualClock
) -> None:
    async with session_factory() as db:
        with pytest.raises(Exception, match="FOREIGN KEY"):
            await users_service.update_profile(
                db, uuid.uuid4(), MyProfileUpdate(display_name="Ghost"), clock=clock
            )
