"""Concurrent writers on one SQLite file, each with its own session and connection.

The pause keeps a transaction open so the second writer really overlaps with it.
"""

import asyncio

import pytest
from sqlalchemy import text

from taxi_service.database.session import SessionFactory

OVERLAP_SECONDS = 0.1


@pytest.fixture
async def offer(session_factory: SessionFactory) -> None:
    async with session_factory.begin() as session:
        await session.execute(
            text("CREATE TABLE offer (id INTEGER PRIMARY KEY, status TEXT NOT NULL, driver TEXT)")
        )
        await session.execute(text("INSERT INTO offer (id, status) VALUES (1, 'offered')"))


async def accept_conditionally(session_factory: SessionFactory, driver: str) -> bool:
    async with session_factory.begin() as session:
        result = await session.execute(
            text(
                "UPDATE offer SET status = 'accepted', driver = :driver "
                "WHERE id = 1 AND status = 'offered' RETURNING id"
            ),
            {"driver": driver},
        )
        await asyncio.sleep(OVERLAP_SECONDS)
        return result.scalar_one_or_none() is not None


async def accept_after_reading(session_factory: SessionFactory, driver: str) -> bool:
    async with session_factory.begin() as session:
        status = await session.scalar(text("SELECT status FROM offer WHERE id = 1"))
        await asyncio.sleep(OVERLAP_SECONDS)
        if status != "offered":
            return False
        await session.execute(
            text("UPDATE offer SET status = 'accepted', driver = :driver WHERE id = 1"),
            {"driver": driver},
        )
        return True


async def accepted_driver(session_factory: SessionFactory) -> str | None:
    async with session_factory() as session:
        driver: str | None = await session.scalar(
            text("SELECT driver FROM offer WHERE id = 1 AND status = 'accepted'")
        )
        return driver


@pytest.mark.usefixtures("offer")
async def test_concurrent_conditional_updates_have_one_winner(
    session_factory: SessionFactory,
) -> None:
    results = await asyncio.gather(
        accept_conditionally(session_factory, "first"),
        accept_conditionally(session_factory, "second"),
    )

    assert sorted(results) == [False, True]
    assert await accepted_driver(session_factory) == ("first" if results[0] else "second")


@pytest.mark.usefixtures("offer")
async def test_transaction_reads_are_serialized_with_concurrent_writes(
    session_factory: SessionFactory,
) -> None:
    results = await asyncio.gather(
        accept_after_reading(session_factory, "first"),
        accept_after_reading(session_factory, "second"),
    )

    assert sorted(results) == [False, True]
    assert await accepted_driver(session_factory) == ("first" if results[0] else "second")
