from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.pool import ConnectionPoolEntry, PoolResetState

BUSY_TIMEOUT_MS = 5000
READ_ONLY_OPTION = "taxi_read_only"
_QUERY_ONLY_KEY = "taxi_query_only"


def configure_sqlite_engine(engine: Engine, *, enforce_foreign_keys: bool = True) -> None:
    # BEGIN IMMEDIATE serializes writers; READ_ONLY_OPTION reads a WAL snapshot with query_only.
    event.listen(engine, "connect", partial(_on_connect, enforce_foreign_keys=enforce_foreign_keys))
    event.listen(engine, "begin", _on_begin)
    event.listen(engine, "reset", _on_reset)


def check_foreign_keys(connection: Connection) -> None:
    """Raise if any row references a missing parent (``PRAGMA foreign_key_check``)."""
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        tables = sorted({str(row[0]) for row in violations})
        raise RuntimeError(f"Broken foreign key references in tables: {', '.join(tables)}")


def sqlite_file_missing(url: URL) -> bool:
    database = url.database
    if url.get_backend_name() != "sqlite" or database in (None, "", ":memory:"):
        return False
    return not Path(database).exists()


def _on_connect(
    dbapi_connection: Any, _record: ConnectionPoolEntry, *, enforce_foreign_keys: bool
) -> None:
    dbapi_connection.create_function(
        "unicode_casefold",
        1,
        lambda value: value.casefold() if value is not None else None,
        deterministic=True,
    )
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA foreign_keys={'ON' if enforce_foreign_keys else 'OFF'}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _on_begin(connection: Connection) -> None:
    options = connection.get_execution_options()
    if "isolation_level" in options:
        raise ValueError(
            "isolation_level execution options are not supported on SQLite here; "
            "use session.begin() or read_transaction()"
        )
    if options.get(READ_ONLY_OPTION):
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
