from sqlalchemy.exc import IntegrityError


def violates_unique(error: IntegrityError, *, constraint: str, table: str, column: str) -> bool:
    # PostgreSQL names the constraint, SQLite names table.column.
    message = str(error.orig)
    return constraint in message or f"UNIQUE constraint failed: {table}.{column}" in message
