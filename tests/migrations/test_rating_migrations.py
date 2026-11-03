"""Ratings revision (ADR 0013): two new tables, nothing else changes.

Relative targets (``<revision>-1``) keep the test independent of where the
revision sits in the history.
"""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from taxi_service.database.migrations import alembic_config
from taxi_service.database.session import create_database_engine

RATINGS_REVISION = "d9f6c93e85a9"
BEFORE_RATINGS = f"{RATINGS_REVISION}-1"
RATING_TABLES = "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'ride_rating%'"
USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'rating-migrations.db'}", configure_logging=False
    )


def execute(config: Config, sql: str) -> list[tuple[object, ...]]:
    async def run() -> list[tuple[object, ...]]:
        engine = create_database_engine(config.attributes["database_url"])
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(sql))
                return [tuple(row) for row in result] if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_creates_the_rating_tables(config: Config) -> None:
    command.upgrade(config, BEFORE_RATINGS)
    assert execute(config, RATING_TABLES) == []

    command.upgrade(config, RATINGS_REVISION)

    assert sorted(execute(config, RATING_TABLES)) == [("ride_rating_tags",), ("ride_ratings",)]


def test_upgrade_downgrade_upgrade_keeps_users_and_leaves_no_schema_diff(config: Config) -> None:
    command.upgrade(config, BEFORE_RATINGS)
    execute(
        config,
        "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
        f" VALUES ('{USER}', 'pat', 'pat', 'hash', 'passenger', '2026-11-03 09:00:00.000000')",
    )

    command.upgrade(config, "head")
    command.downgrade(config, BEFORE_RATINGS)
    assert execute(config, RATING_TABLES) == []
    command.upgrade(config, "head")

    command.check(config)
    assert execute(config, "SELECT username FROM users") == [("pat",)]
