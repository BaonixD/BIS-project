from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select, text
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.database.base import UtcDateTime
from taxi_service.database.session import SessionFactory

ALMATY = timezone(timedelta(hours=5))

metadata = MetaData()
event = Table(
    "event",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("happened_at", UtcDateTime(), nullable=True),
)


@pytest.fixture(autouse=True)
async def _event_table(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)


async def store(session_factory: SessionFactory, value: datetime | None) -> datetime | None:
    async with session_factory.begin() as session:
        await session.execute(insert(event).values(id=1, happened_at=value))
    async with session_factory() as session:
        loaded: datetime | None = await session.scalar(select(event.c.happened_at))
        return loaded


async def test_utc_value_round_trips_as_aware_utc(session_factory: SessionFactory) -> None:
    moment = datetime(2026, 11, 3, 7, 30, 15, 123456, tzinfo=UTC)

    loaded = await store(session_factory, moment)

    assert loaded == moment
    assert loaded is not None
    assert loaded.tzinfo is UTC


async def test_other_offset_is_stored_as_utc(session_factory: SessionFactory) -> None:
    almaty_noon = datetime(2026, 11, 3, 12, 0, tzinfo=ALMATY)

    loaded = await store(session_factory, almaty_noon)

    assert loaded == almaty_noon
    assert loaded is not None
    assert loaded.tzinfo is UTC
    assert loaded.hour == 7
    async with session_factory() as session:
        raw = await session.scalar(text("SELECT happened_at FROM event"))
    assert str(raw).startswith("2026-11-03 07:00:00")


async def test_naive_datetime_is_rejected(session_factory: SessionFactory) -> None:
    with pytest.raises(StatementError, match="timezone-aware"):
        await store(session_factory, datetime(2026, 11, 3, 12, 0))


async def test_null_round_trips(session_factory: SessionFactory) -> None:
    assert await store(session_factory, None) is None


async def test_sql_comparison_uses_utc_instants(session_factory: SessionFactory) -> None:
    await store(session_factory, datetime(2026, 11, 3, 7, 0, tzinfo=UTC))
    # 11:59 in Almaty is 06:59 UTC: earlier than the stored 07:00 UTC.
    bound = datetime(2026, 11, 3, 11, 59, tzinfo=ALMATY)

    async with session_factory() as session:
        later = await session.scalar(select(event.c.id).where(event.c.happened_at > bound))

    assert later == 1
