"""Read path: a DEFERRED, query-only transaction that never takes the write lock."""

import asyncio
import contextlib

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.database.session import SessionFactory, read_transaction

WRITER_HOLD_LIMIT_SECONDS = 1.0


@pytest.fixture(autouse=True)
async def _ledger(session_factory: SessionFactory) -> None:
    async with session_factory.begin() as session:
        await session.execute(text("CREATE TABLE ledger (id INTEGER PRIMARY KEY, note TEXT)"))
        await session.execute(text("INSERT INTO ledger (id, note) VALUES (1, 'committed')"))


async def test_reader_is_not_blocked_by_open_write_transaction(
    session_factory: SessionFactory,
) -> None:
    events: list[str] = []
    writer_holds_lock = asyncio.Event()
    reader_done = asyncio.Event()

    async def writer() -> None:
        async with session_factory.begin() as session:
            await session.execute(text("INSERT INTO ledger (id, note) VALUES (2, 'pending')"))
            writer_holds_lock.set()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(reader_done.wait(), WRITER_HOLD_LIMIT_SECONDS)
            events.append("writer released")

    async def reader() -> None:
        await writer_holds_lock.wait()
        async with session_factory() as session, read_transaction(session):
            rows = await session.scalar(text("SELECT count(*) FROM ledger"))
        events.append(f"reader saw {rows}")
        reader_done.set()

    await asyncio.gather(writer(), reader())

    # The reader finished while the writer still held its transaction open and
    # saw only committed data.
    assert events == ["reader saw 1", "writer released"]


async def test_write_inside_read_transaction_fails(session_factory: SessionFactory) -> None:
    with pytest.raises(OperationalError, match="readonly"):
        async with session_factory() as session, read_transaction(session):
            await session.execute(text("INSERT INTO ledger (id, note) VALUES (3, 'sneaky')"))

    async with session_factory() as session, read_transaction(session):
        assert await session.scalar(text("SELECT count(*) FROM ledger")) == 1


async def test_pooled_connection_is_writable_after_read_transaction(
    engine: AsyncEngine, session_factory: SessionFactory
) -> None:
    async with session_factory() as session, read_transaction(session):
        connection = await session.connection()
        used = connection.sync_connection
        assert used is not None
        read_dbapi = used.connection.dbapi_connection

    def query_only_and_dbapi(sync_connection: Connection) -> tuple[object, object]:
        dbapi = sync_connection.connection.dbapi_connection
        assert dbapi is not None
        cursor = dbapi.cursor()
        cursor.execute("PRAGMA query_only")
        row = cursor.fetchone()
        cursor.close()
        assert row is not None
        return row[0], dbapi

    # Inspect the next checkout directly, before any BEGIN could reset it.
    async with engine.connect() as next_checkout:
        query_only, next_dbapi = await next_checkout.run_sync(query_only_and_dbapi)

    assert next_dbapi is read_dbapi
    assert query_only == 0
    async with session_factory.begin() as session:
        await session.execute(text("INSERT INTO ledger (id, note) VALUES (4, 'after read')"))
