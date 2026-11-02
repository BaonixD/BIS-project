import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import SessionFactory


async def pragma(session_factory: SessionFactory, name: str) -> object:
    async with session_factory() as session:
        return await session.scalar(text(f"PRAGMA {name}"))


async def test_foreign_keys_are_enforced(session_factory: SessionFactory) -> None:
    async with session_factory.begin() as session:
        await session.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        await session.execute(
            text("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent)")
        )

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        async with session_factory.begin() as session:
            await session.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 42)"))


async def test_every_connection_has_foreign_keys_enabled(session_factory: SessionFactory) -> None:
    async def foreign_keys_on_own_connection() -> object:
        async with session_factory() as session:
            value = await session.scalar(text("PRAGMA foreign_keys"))
            await asyncio.sleep(0.05)  # keep this connection checked out
            return value

    # Overlapping sessions cannot share a pooled connection.
    values = await asyncio.gather(
        foreign_keys_on_own_connection(), foreign_keys_on_own_connection()
    )
    assert list(values) == [1, 1]


async def test_journal_mode_is_wal(session_factory: SessionFactory) -> None:
    assert await pragma(session_factory, "journal_mode") == "wal"


async def test_busy_timeout_waits_for_locks(session_factory: SessionFactory) -> None:
    assert await pragma(session_factory, "busy_timeout") == 5000
