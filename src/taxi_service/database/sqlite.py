"""SQLite connection setup shared by the application, tests and Alembic."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import ConnectionPoolEntry

BUSY_TIMEOUT_MS = 5000


def configure_sqlite_engine(engine: Engine) -> None:
    """Make SQLite transactions real and serialized; enforce foreign keys.

    The ``sqlite3`` driver under aiosqlite defers ``BEGIN`` until the first
    INSERT/UPDATE/DELETE, so a transaction's SELECTs run outside it and two
    read-then-write transactions both act on stale data. Driver-managed
    transactions are therefore switched off (``isolation_level = None``) and
    SQLAlchemy emits ``BEGIN IMMEDIATE`` itself: it takes the write lock at the
    start, so concurrent transactions wait (up to ``busy_timeout``) and run one
    after another.

    Consequence for callers: every transaction, even a read-only one, holds the
    database write lock until it ends. Keep transactions short, never await
    external services inside one, and never open a second session while the
    current task still has a transaction open: it would wait for itself.
    """
    event.listen(engine, "connect", _on_connect)
    event.listen(engine, "begin", _on_begin)


def _on_connect(dbapi_connection: Any, _record: ConnectionPoolEntry) -> None:
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _on_begin(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN IMMEDIATE")
