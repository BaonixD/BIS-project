"""SQLite connection setup shared by the application, tests and Alembic."""

from functools import partial
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import ConnectionPoolEntry, PoolResetState

BUSY_TIMEOUT_MS = 5000
READ_ONLY_OPTION = "taxi_read_only"
"""Execution option selecting the read path; set it before the transaction begins."""
_QUERY_ONLY_KEY = "taxi_query_only"


def configure_sqlite_engine(engine: Engine, *, enforce_foreign_keys: bool = True) -> None:
    """Make SQLite transactions real and serialized; enforce foreign keys.

    The ``sqlite3`` driver under aiosqlite defers ``BEGIN`` until the first
    INSERT/UPDATE/DELETE, so a transaction's SELECTs run outside it and two
    read-then-write transactions both act on stale data. Driver-managed
    transactions are therefore switched off (``isolation_level = None``) and
    SQLAlchemy emits ``BEGIN IMMEDIATE`` itself: it takes the write lock at the
    start, so concurrent transactions wait (up to ``busy_timeout``) and run one
    after another.

    A connection with the ``READ_ONLY_OPTION`` execution option instead begins a
    plain (DEFERRED) transaction with ``PRAGMA query_only=ON``: in WAL mode it
    reads a committed snapshot without waiting for writers, and any write in it
    fails. ``query_only`` is switched off again when the connection returns to
    the pool and before any later write transaction on it.

    Consequence for callers: every transaction, even a read-only one, holds the
    database write lock until it ends. Keep transactions short, never await
    external services inside one, and never open a second session while the
    current task still has a transaction open: it would wait for itself.

    ``enforce_foreign_keys=False`` is only for migrations: rebuilding a table
    (copy, DROP, RENAME) with enforcement on cascades the DROP to related rows.
    Such a transaction must end with :func:`check_foreign_keys`.
    """
    event.listen(engine, "connect", partial(_on_connect, enforce_foreign_keys=enforce_foreign_keys))
    event.listen(engine, "begin", _on_begin)
    event.listen(engine, "reset", _on_reset)


def check_foreign_keys(connection: Connection) -> None:
    """Raise if any row references a missing parent (``PRAGMA foreign_key_check``)."""
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        tables = sorted({str(row[0]) for row in violations})
        raise RuntimeError(f"Broken foreign key references in tables: {', '.join(tables)}")


def _on_connect(
    dbapi_connection: Any, _record: ConnectionPoolEntry, *, enforce_foreign_keys: bool
) -> None:
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA foreign_keys={'ON' if enforce_foreign_keys else 'OFF'}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _on_begin(connection: Connection) -> None:
    if connection.get_execution_options().get(READ_ONLY_OPTION):
        connection.info[_QUERY_ONLY_KEY] = True
        connection.exec_driver_sql("PRAGMA query_only=ON")
        connection.exec_driver_sql("BEGIN DEFERRED")
        return
    if connection.info.pop(_QUERY_ONLY_KEY, False):
        connection.exec_driver_sql("PRAGMA query_only=OFF")
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def _on_reset(
    dbapi_connection: Any, record: ConnectionPoolEntry, reset_state: PoolResetState
) -> None:
    # Without asyncio safety the pool discards the connection instead of reusing it.
    if not record.info.get(_QUERY_ONLY_KEY) or not reset_state.asyncio_safe:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA query_only=OFF")
    finally:
        cursor.close()
    del record.info[_QUERY_ONLY_KEY]
