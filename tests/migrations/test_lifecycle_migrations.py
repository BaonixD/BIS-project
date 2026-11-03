"""T07B revision on a database with rides: new columns are empty, downgrade keeps rides."""

import asyncio
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from taxi_service.database.migrations import alembic_config
from taxi_service.database.session import create_database_engine

T06_HEAD = "5d2e4cb65b5e"
USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
QUOTE = "1f1e2d3c4b5a69788796a5b4c3d2e1f0"
RIDE = "2f1e2d3c4b5a69788796a5b4c3d2e1f0"
SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
SNAPSHOT_VALUES = "76.95, 43.23, 76.92, 43.21, 10000, 1500, '{}', 'fake', 2200, 'KZT', 'edu-v1'"
NEW_RIDE_COLUMNS = (
    "assigned_at",
    "arrived_at",
    "started_at",
    "completed_at",
    "cancelled_at",
    "cancel_reason",
)
RIDES_INDEXES = (
    "SELECT name, sql FROM sqlite_master WHERE tbl_name = 'rides' AND type = 'index' ORDER BY name"
)
RIDES_TABLE = "SELECT sql FROM sqlite_master WHERE name = 'rides' AND type = 'table'"
# Every named constraint of rides at T06 head, CHECKs, UNIQUE quote and keys included.
T06_RIDES_CONSTRAINTS = {
    "pk_rides",
    "uq_rides_quote_id",
    "fk_rides_passenger_id_users",
    "fk_rides_driver_id_driver_profiles",
    "fk_rides_quote_id_ride_quotes",
    "ck_rides_longitude_range",
    "ck_rides_latitude_range",
    "ck_rides_route_metrics",
    "ck_rides_amount_positive",
    "ck_rides_currency_kzt",
    "ck_rides_status",
    "ck_rides_driver_matches_status",
    "ck_rides_search_deadline_after_start",
}


def rides_table_sql(config: Config) -> str:
    [(sql,)] = execute(config, RIDES_TABLE)
    assert isinstance(sql, str)
    return sql


def rides_constraints(config: Config) -> dict[str, str]:
    """Name -> definition of every named constraint in the rides CREATE TABLE."""
    constraints = {}
    for line in rides_table_sql(config).splitlines():
        part = line.strip().rstrip(",")
        if part.startswith("CONSTRAINT "):
            _, name, definition = part.split(" ", 2)
            constraints[name] = " ".join(definition.split())
    return constraints


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'lifecycle-migrations.db'}", configure_logging=False
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


def insert_t06_ride(config: Config) -> None:
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
        f" search_started_at, search_deadline, {SNAPSHOT_COLUMNS}) VALUES ('{RIDE}', '{USER}',"
        f" '{QUOTE}', 'cancelled', '2026-11-03 09:01:00.000000', '2026-11-03 09:01:00.000000',"
        f" '2026-11-03 09:01:00.000000', '2026-11-03 09:04:00.000000', {SNAPSHOT_VALUES})",
    )


def test_existing_rides_get_empty_lifecycle_columns(config: Config) -> None:
    command.upgrade(config, T06_HEAD)
    insert_t06_ride(config)

    command.upgrade(config, "head")

    columns = ", ".join(NEW_RIDE_COLUMNS)
    assert execute(config, f"SELECT id, {columns} FROM rides") == [
        (RIDE, *(None,) * len(NEW_RIDE_COLUMNS))
    ]
    assert execute(config, "SELECT count(*) FROM ride_events") == [(0,)]
    command.check(config)


def test_downgrade_to_t06_keeps_rides_and_their_constraints(config: Config) -> None:
    command.upgrade(config, T06_HEAD)
    t06_indexes = execute(config, RIDES_INDEXES)
    t06_constraints = rides_constraints(config)
    assert set(t06_constraints) == T06_RIDES_CONSTRAINTS
    insert_t06_ride(config)
    command.upgrade(config, "head")

    command.downgrade(config, T06_HEAD)

    assert execute(config, "SELECT id, status FROM rides") == [(RIDE, "cancelled")]
    assert execute(config, "SELECT name FROM sqlite_master WHERE name = 'ride_events'") == []
    assert execute(config, RIDES_INDEXES) == t06_indexes
    assert rides_constraints(config) == t06_constraints
    table_sql = rides_table_sql(config)
    assert not any(re.search(rf"\b{column}\b", table_sql) for column in NEW_RIDE_COLUMNS)
    command.upgrade(config, "head")
    command.check(config)
