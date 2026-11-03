"""Tariff revision (ADR 0012) on a database with a quote, a ride and a vehicle.

Relative targets (``<revision>-1``) keep the test independent of where the
revision sits in the history.
"""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.migrations import alembic_config
from taxi_service.database.session import create_database_engine

TARIFF_REVISION = "4dc8bde81ded"
BEFORE_TARIFFS = f"{TARIFF_REVISION}-1"
PASSENGER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
DRIVER = "1f1e2d3c4b5a69788796a5b4c3d2e1f0"
QUOTE = "2f1e2d3c4b5a69788796a5b4c3d2e1f0"
RIDE = "3f1e2d3c4b5a69788796a5b4c3d2e1f0"
VEHICLE = "4f1e2d3c4b5a69788796a5b4c3d2e1f0"
AT = "2026-11-03 09:00:00.000000"
OLD_SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
OLD_SNAPSHOT = "76.95, 43.23, 76.92, 43.21, 10000, 1500, '{}', 'fake', 2200, 'KZT', 'edu-v1'"
AMOUNT_COLUMNS = (
    "economy_amount_kzt",
    "comfort_amount_kzt",
    "comfort_plus_amount_kzt",
    "business_amount_kzt",
)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'tariff-migrations.db'}", configure_logging=False
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


def columns(config: Config, table: str) -> set[str]:
    return {str(row[1]) for row in execute(config, f"PRAGMA table_info({table})")}


@pytest.fixture
def old_rows(config: Config) -> Config:
    """Before tariffs: a passenger's edu-v1 quote and ride, a driver with a vehicle."""
    command.upgrade(config, BEFORE_TARIFFS)
    for user_id, name, role in ((PASSENGER, "pat", "passenger"), (DRIVER, "dana", "driver")):
        execute(
            config,
            "INSERT INTO users (id, username, username_normalized, password_hash, role,"
            f" created_at) VALUES ('{user_id}', '{name}', '{name}', 'hash', '{role}', '{AT}')",
        )
    execute(
        config,
        "INSERT INTO driver_profiles (user_id, approval_status, is_online, created_at,"
        f" updated_at) VALUES ('{DRIVER}', 'pending', 0, '{AT}', '{AT}')",
    )
    execute(
        config,
        "INSERT INTO vehicles (id, driver_id, make, model, color, plate_number, year, updated_at)"
        f" VALUES ('{VEHICLE}', '{DRIVER}', 'Kia', 'K5', 'black', '123ABC02', 2020, '{AT}')",
    )
    execute(
        config,
        "INSERT INTO ride_quotes (id, passenger_id, created_at, expires_at,"
        f" {OLD_SNAPSHOT_COLUMNS}) VALUES ('{QUOTE}', '{PASSENGER}', '{AT}',"
        f" '2026-11-03 09:05:00.000000', {OLD_SNAPSHOT})",
    )
    execute(
        config,
        "INSERT INTO rides (id, passenger_id, driver_id, quote_id, status, created_at,"
        f" updated_at, search_started_at, search_deadline, {OLD_SNAPSHOT_COLUMNS}) VALUES"
        f" ('{RIDE}', '{PASSENGER}', NULL, '{QUOTE}', 'no_driver', '{AT}', '{AT}', '{AT}',"
        f" '2026-11-03 09:03:00.000000', {OLD_SNAPSHOT})",
    )
    return config


def test_upgrade_prices_old_quotes_and_marks_rides_and_cars_economy(old_rows: Config) -> None:
    command.upgrade(old_rows, TARIFF_REVISION)

    assert "amount_kzt" not in columns(old_rows, "ride_quotes")
    assert execute(
        old_rows, f"SELECT {', '.join(AMOUNT_COLUMNS)}, tariff_version FROM ride_quotes"
    ) == [(2200, 2925, 3650, 4800, "edu-v1")]
    assert execute(old_rows, "SELECT tariff, amount_kzt FROM rides") == [("economy", 2200)]
    assert execute(old_rows, "SELECT car_class FROM vehicles") == [("economy",)]


def test_upgraded_tables_check_tariffs_and_classes(old_rows: Config) -> None:
    command.upgrade(old_rows, TARIFF_REVISION)

    with pytest.raises(IntegrityError, match="CHECK"):
        execute(old_rows, "UPDATE rides SET tariff = 'premium'")
    with pytest.raises(IntegrityError, match="CHECK"):
        execute(old_rows, "UPDATE vehicles SET car_class = 'premium'")
    with pytest.raises(IntegrityError, match="CHECK"):
        execute(old_rows, "UPDATE ride_quotes SET business_amount_kzt = 0")


def test_downgrade_keeps_the_economy_price(old_rows: Config) -> None:
    command.upgrade(old_rows, TARIFF_REVISION)
    execute(old_rows, "UPDATE vehicles SET car_class = 'business'")

    command.downgrade(old_rows, BEFORE_TARIFFS)

    assert not set(AMOUNT_COLUMNS) & columns(old_rows, "ride_quotes")
    assert "tariff" not in columns(old_rows, "rides")
    assert "car_class" not in columns(old_rows, "vehicles")
    assert execute(old_rows, "SELECT amount_kzt FROM ride_quotes") == [(2200,)]
    with pytest.raises(IntegrityError, match="CHECK"):
        execute(old_rows, "UPDATE ride_quotes SET amount_kzt = 0")


def test_upgrade_downgrade_upgrade_leaves_no_schema_diff(old_rows: Config) -> None:
    command.upgrade(old_rows, "head")
    command.downgrade(old_rows, BEFORE_TARIFFS)
    command.upgrade(old_rows, "head")

    command.check(old_rows)
    assert execute(old_rows, "SELECT tariff FROM rides") == [("economy",)]
