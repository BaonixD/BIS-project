"""Indexes created by ``alembic upgrade head`` match the ORM models, WHERE clauses included.

``alembic check`` does not compare the predicate of a partial index, and a SQLite
batch rebuild recreates indexes from reflection; this test reads ``sqlite_master``
of the migrated database instead. Every partial index must also keep the same
predicate on PostgreSQL and never depend on the current time.
"""

import re
from dataclasses import dataclass

import pytest
from sqlalchemy import Index, Table, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.schema import CreateIndex

from taxi_service.database.metadata import target_metadata

# Indexes later tasks rely on; the comparison below covers every model index.
REQUIRED_INDEXES = {
    "uq_rides_active_passenger_id",
    "uq_rides_active_driver_id",
    "ix_rides_passenger_id_created_at",
    "ix_rides_driver_id_created_at",
    "ix_rides_searching_search_deadline",
    "uq_ride_offers_pending_ride_id",
    "uq_ride_offers_pending_driver_id",
    "ix_ride_offers_pending_expires_at",
    "ix_ride_events_ride_id_created_at",
    "ix_payment_events_payment_id_created_at",
}
TIME_FUNCTIONS = re.compile(r"now|current_|date|time|julianday", re.IGNORECASE)


@dataclass(frozen=True)
class IndexShape:
    table: str
    columns: tuple[str, ...]
    unique: bool
    where: str | None


def normalize(sql: str) -> str:
    return " ".join(sql.replace('"', "").split())


def model_indexes() -> dict[str, tuple[Index, IndexShape]]:
    found: dict[str, tuple[Index, IndexShape]] = {}
    for table in target_metadata.tables.values():
        for index in table.indexes:
            assert isinstance(index.table, Table)
            assert isinstance(index.name, str)
            where = index.dialect_options["sqlite"]["where"]
            shape = IndexShape(
                table=index.table.name,
                columns=tuple(column.name for column in index.columns),
                unique=bool(index.unique),
                where=None if where is None else normalize(str(where)),
            )
            found[index.name] = (index, shape)
    return found


async def database_indexes(engine: AsyncEngine) -> dict[str, IndexShape]:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'index'")
            )
        ).all()
        found = {}
        for name, table, sql in rows:
            if sql is None:  # automatic index of a UNIQUE constraint or primary key
                continue
            columns = await connection.execute(text(f'PRAGMA index_info("{name}")'))
            definition, _, where = normalize(sql).partition(" WHERE ")
            found[name] = IndexShape(
                table=table,
                columns=tuple(row[2] for row in columns),
                unique=definition.upper().startswith("CREATE UNIQUE INDEX"),
                where=where or None,
            )
    return found


async def test_required_indexes_exist_after_upgrade(engine: AsyncEngine) -> None:
    assert set(await database_indexes(engine)) >= REQUIRED_INDEXES


async def test_every_model_index_matches_the_migrated_database(engine: AsyncEngine) -> None:
    expected = {name: shape for name, (_, shape) in model_indexes().items()}

    assert await database_indexes(engine) == expected


@pytest.mark.parametrize("name", sorted(model_indexes()))
def test_partial_index_predicate_is_portable_and_timeless(name: str) -> None:
    index, shape = model_indexes()[name]
    postgresql_where = index.dialect_options["postgresql"]["where"]

    if shape.where is None:
        assert postgresql_where is None
        return
    assert postgresql_where is not None
    assert normalize(str(postgresql_where)) == shape.where
    assert not TIME_FUNCTIONS.search(shape.where)
    for backend in ("sqlite", "postgresql"):
        dialect = URL.create(backend).get_dialect()()
        ddl = normalize(str(CreateIndex(index).compile(dialect=dialect)))
        assert ddl.endswith(f"WHERE {shape.where}")
