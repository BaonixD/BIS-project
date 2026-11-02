"""``user_profiles`` CHECK constraints hold even when the API validation is bypassed."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import SessionFactory

INSERT_USER = (
    "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
    " VALUES (:id, :name, :name, 'hash', 'passenger', '2026-11-03 09:00:00.000000')"
)
INSERT_PROFILE = (
    "INSERT INTO user_profiles (user_id, display_name, phone, updated_at)"
    " VALUES (:id, :display_name, :phone, '2026-11-03 09:00:00.000000')"
)


async def insert_profile(
    session_factory: SessionFactory, display_name: str | None, phone: str | None
) -> None:
    user_id = uuid.uuid4().hex
    async with session_factory.begin() as session:
        await session.execute(text(INSERT_USER), {"id": user_id, "name": f"u{user_id[:8]}"})
        await session.execute(
            text(INSERT_PROFILE), {"id": user_id, "display_name": display_name, "phone": phone}
        )


async def test_valid_and_empty_profiles_are_stored(session_factory: SessionFactory) -> None:
    await insert_profile(session_factory, "Alice", "+77011234567")
    await insert_profile(session_factory, None, None)


@pytest.mark.parametrize(
    ("display_name", "phone"),
    [("", None), ("x" * 65, None), (None, "77011234567"), (None, "+7701"), (None, "+" + "1" * 16)],
)
async def test_malformed_values_are_rejected(
    session_factory: SessionFactory, display_name: str | None, phone: str | None
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_profile(session_factory, display_name, phone)
