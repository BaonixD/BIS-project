"""Autogenerate output for project column types."""

from alembic.autogenerate import compare_metadata, render_python_code
from alembic.operations import ops
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.database.base import UtcDateTime
from taxi_service.database.migrations import render_item


def event_table(metadata: MetaData) -> Table:
    return Table(
        "event",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("happened_at", UtcDateTime(), nullable=False),
    )


def test_utc_datetime_renders_as_portable_sqlalchemy_type() -> None:
    upgrade = ops.UpgradeOps([ops.CreateTableOp.from_table(event_table(MetaData()))])

    code = render_python_code(upgrade, render_as_batch=True, render_item=render_item)

    # Migrations must not import application code that may change later.
    assert "sa.DateTime(timezone=True)" in code
    assert "taxi_service" not in code


async def test_rendered_column_matches_model_without_diff(engine: AsyncEngine) -> None:
    created = MetaData()
    Table(
        "event",
        created,
        Column("id", Integer, primary_key=True),
        Column("happened_at", UtcDateTime().impl, nullable=False),
    )
    async with engine.begin() as connection:
        await connection.run_sync(created.create_all)

    def diff(sync_connection: Connection) -> list[object]:
        context = MigrationContext.configure(sync_connection, opts={"render_as_batch": True})
        model = MetaData()
        event_table(model)
        return list(compare_metadata(context, model))

    async with engine.connect() as connection:
        assert await connection.run_sync(diff) == []
