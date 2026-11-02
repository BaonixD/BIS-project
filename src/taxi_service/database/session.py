from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
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
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()
