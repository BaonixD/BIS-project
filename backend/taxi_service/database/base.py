from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Dialect, MetaData, TypeDecorator
from sqlalchemy.orm import DeclarativeBase

# Stable, predictable names so migrations can refer to constraints on any database.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UtcDateTime(TypeDecorator[datetime]):
    # SQLite keeps no offset: store UTC so text comparison stays chronological.

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UtcDateTime requires a timezone-aware datetime")
        utc_value = value.astimezone(UTC)
        return utc_value.replace(tzinfo=None) if dialect.name == "sqlite" else utc_value

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"Unexpected value type for UtcDateTime: {type(value).__name__}")
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
