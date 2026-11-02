"""T06 revisions on a database with rides: the search window is filled, downgrade keeps rides."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from taxi_service.database.migrations import alembic_config
from taxi_service.database.session import create_database_engine

T05_HEAD = "640cf8e50671"
USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
QUOTE = "1f1e2d3c4b5a69788796a5b4c3d2e1f0"
RIDE = "2f1e2d3c4b5a69788796a5b4c3d2e1f0"
SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
SNAPSHOT_VALUES = "76.95, 43.23, 76.92, 43.21, 10000, 1500, '{}', 'fake', 2200, 'KZT', 'edu-v1'"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'dispatch-migrations.db'}", configure_logging=False
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


def insert_t05_ride(config: Config) -> None:
    execute(
        config,
        "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
        f" VALUES ('{USER}', 'pat', 'pat', 'hash', 'passenger', '2026-11-03 09:00:00.000000')",
    )
    execute(
        config,
        f"INSERT INTO ride_quotes (id, passenger_id, created_at, expires_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{QUOTE}', '{USER}', '2026-11-03 09:00:00.000000',"
        f" '2026-11-03 09:05:00.000000', {SNAPSHOT_VALUES})",
    )
    execute(
        config,
        "INSERT INTO rides (id, passenger_id, quote_id, status, created_at, updated_at,"
        f" {SNAPSHOT_COLUMNS}) VALUES ('{RIDE}', '{USER}', '{QUOTE}', 'searching',"
        f" '2026-11-03 09:01:00.000000', '2026-11-03 09:01:00.000000', {SNAPSHOT_VALUES})",
    )


def test_existing_rides_get_a_180_second_search_window(config: Config) -> None:
    command.upgrade(config, T05_HEAD)
    insert_t05_ride(config)

    command.upgrade(config, "head")

    assert execute(config, "SELECT search_started_at, search_deadline FROM rides") == [
        ("2026-11-03 09:01:00.000000", "2026-11-03 09:04:00.000000")
    ]
    command.check(config)


def test_downgrade_to_t05_keeps_rides_and_drops_offers(config: Config) -> None:
    command.upgrade(config, T05_HEAD)
    insert_t05_ride(config)
    command.upgrade(config, "head")

    command.downgrade(config, T05_HEAD)

    assert execute(config, "SELECT id, status FROM rides") == [(RIDE, "searching")]
    tables = execute(config, "SELECT name FROM sqlite_master WHERE name = 'ride_offers'")
    assert tables == []
    command.upgrade(config, "head")
    command.check(config)
