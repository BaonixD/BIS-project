"""Database constraints of ``users``: they hold even when Python checks are bypassed."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.users.models import User, UserRole

CREATED_AT = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def user(username: str, role: UserRole = UserRole.PASSENGER) -> User:
    return User(
        username=username,
        username_normalized=username.lower(),
        password_hash="$argon2id$placeholder",
        role=role,
        created_at=CREATED_AT,
    )


async def insert_raw(
    session_factory: SessionFactory, username: str, normalized: str, role: str
) -> None:
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, username, username_normalized, password_hash, role,"
                " created_at) VALUES (:id, :username, :normalized, 'hash', :role, :created_at)"
            ),
            {
                "id": uuid.uuid4().hex,
                "username": username,
                "normalized": normalized,
                "role": role,
                "created_at": "2026-11-03 09:00:00.000000",
            },
        )


async def test_user_round_trip(session_factory: SessionFactory) -> None:
    async with session_factory.begin() as session:
        session.add(user("Alice_01", UserRole.DRIVER))

    async with session_factory() as session, read_transaction(session):
        stored = (await session.scalars(select(User))).one()

    assert (stored.username, stored.username_normalized) == ("Alice_01", "alice_01")
    assert stored.role is UserRole.DRIVER
    assert stored.created_at == CREATED_AT


async def test_usernames_differing_only_in_case_are_rejected(
    session_factory: SessionFactory,
) -> None:
    async with session_factory.begin() as session:
        session.add(user("alice"))

    with pytest.raises(IntegrityError, match="UNIQUE"):
        async with session_factory.begin() as session:
            session.add(user("ALICE"))


async def test_normalized_username_must_be_lower_case_username(
    session_factory: SessionFactory,
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_raw(session_factory, "Alice", "Alice", "passenger")


async def test_unknown_role_is_rejected(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_raw(session_factory, "alice", "alice", "superuser")
