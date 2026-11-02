from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

SessionFactory = async_sessionmaker[AsyncSession]

SQLITE_BUSY_TIMEOUT_MS = 5000


def create_database_engine(url: str) -> AsyncEngine:
    """Create the application engine; the caller owns it and must ``dispose()`` it."""
    engine = create_async_engine(url)
    if engine.dialect.name == "sqlite":
        _configure_sqlite(engine.sync_engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Sessions keep loaded attributes after commit so responses need no extra SQL."""
    return async_sessionmaker(engine, expire_on_commit=False)


def _configure_sqlite(engine: Engine) -> None:
    """Make SQLite transactions real and serialized.

    The ``sqlite3`` driver under aiosqlite defers ``BEGIN`` until the first
    INSERT/UPDATE/DELETE, so a transaction's SELECTs run outside it and two
    read-then-write transactions both act on stale data. Driver-managed
    transactions are therefore switched off (``isolation_level = None``) and
    SQLAlchemy emits ``BEGIN IMMEDIATE`` itself: it takes the write lock at the
    start, so concurrent transactions wait (up to ``busy_timeout``) and run one
    after another. Readers in the same transaction see a stable snapshot.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: ConnectionPoolEntry) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
