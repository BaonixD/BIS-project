from sqlalchemy.exc import IntegrityError


def violates_unique(error: IntegrityError, *, constraint: str, table: str, column: str) -> bool:
    """Whether ``error`` is this unique constraint failing.

    PostgreSQL names the constraint in the message; SQLite names the column as
    ``table.column``. Map only what is recognized and re-raise everything else.
    """
    message = str(error.orig)
    return constraint in message or f"UNIQUE constraint failed: {table}.{column}" in message
