"""T08B revision on a database with rides: completed rides get their unpaid cash payment."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from taxi_service.database.migrations import alembic_config
from taxi_service.database.session import create_database_engine

T07_HEAD = "b42082a5b952"
USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
DRIVER = "3f1e2d3c4b5a69788796a5b4c3d2e1f0"
COMPLETED_RIDE = "2f1e2d3c4b5a69788796a5b4c3d2e1f0"
CANCELLED_RIDE = "4f1e2d3c4b5a69788796a5b4c3d2e1f0"
COMPLETED_AT = "2026-11-03 09:30:00.000000"
SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
PAYMENT_TABLES = "SELECT name FROM sqlite_master WHERE name IN ('payments', 'payment_events')"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'payment-migrations.db'}", configure_logging=False
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


def insert_user(config: Config, user_id: str, username: str, role: str) -> None:
    execute(
        config,
        "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
        f" VALUES ('{user_id}', '{username}', '{username}', 'hash', '{role}',"
        " '2026-11-03 09:00:00.000000')",
    )


def insert_ride(config: Config, ride_id: str, *, status: str, amount_kzt: int) -> None:
    quote_id = ride_id[::-1]
    snapshot = f"76.95, 43.23, 76.92, 43.21, 10000, 1500, '{{}}', 'fake', {amount_kzt}, 'KZT', 'v1'"
    execute(
        config,
        f"INSERT INTO ride_quotes (id, passenger_id, created_at, expires_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{quote_id}', '{USER}', '2026-11-03 09:00:00.000000',"
        f" '2026-11-03 09:05:00.000000', {snapshot})",
    )
    completed_at = f"'{COMPLETED_AT}'" if status == "completed" else "NULL"
    execute(
        config,
        "INSERT INTO rides (id, passenger_id, driver_id, quote_id, status, created_at,"
        f" updated_at, search_started_at, search_deadline, completed_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{ride_id}', '{USER}', '{DRIVER}', '{quote_id}', '{status}',"
        " '2026-11-03 09:01:00.000000', '2026-11-03 09:31:00.000000',"
        " '2026-11-03 09:01:00.000000', '2026-11-03 09:04:00.000000',"
        f" {completed_at}, {snapshot})",
    )


def insert_t07_rides(config: Config) -> None:
    insert_user(config, USER, "pat", "passenger")
    insert_user(config, DRIVER, "dana", "driver")
    execute(
        config,
        "INSERT INTO driver_profiles (user_id, approval_status, is_online, created_at, updated_at)"
        f" VALUES ('{DRIVER}', 'pending', 0, '2026-11-03 09:00:00.000000',"
        " '2026-11-03 09:00:00.000000')",
    )
    insert_ride(config, COMPLETED_RIDE, status="completed", amount_kzt=3100)
    insert_ride(config, CANCELLED_RIDE, status="cancelled", amount_kzt=2200)


def test_completed_rides_get_an_unpaid_cash_payment(config: Config) -> None:
    command.upgrade(config, T07_HEAD)
    insert_t07_rides(config)

    command.upgrade(config, "head")

    assert execute(
        config,
        "SELECT ride_id, amount_kzt, currency, method, status, verification, reported_at,"
        " confirmed_at, confirmed_by, created_at, updated_at FROM payments",
    ) == [
        (
            COMPLETED_RIDE,
            3100,
            "KZT",
            "cash",
            "unpaid",
            "manual",
            None,
            None,
            None,
            COMPLETED_AT,
            COMPLETED_AT,
        )
    ]
    assert execute(
        config,
        "SELECT p.ride_id, e.action, e.from_status, e.to_status, e.from_method, e.to_method,"
        " e.actor_id, e.reference, e.created_at"
        " FROM payment_events e JOIN payments p ON p.id = e.payment_id",
    ) == [(COMPLETED_RIDE, "open", None, "unpaid", None, "cash", None, None, COMPLETED_AT)]
    command.check(config)


def test_downgrade_to_t07_drops_payments_and_keeps_rides(config: Config) -> None:
    command.upgrade(config, T07_HEAD)
    insert_t07_rides(config)
    command.upgrade(config, "head")

    command.downgrade(config, T07_HEAD)

    assert execute(config, PAYMENT_TABLES) == []
    assert execute(config, "SELECT id, status FROM rides ORDER BY id") == [
        (COMPLETED_RIDE, "completed"),
        (CANCELLED_RIDE, "cancelled"),
    ]
    command.upgrade(config, "head")
    assert execute(config, "SELECT ride_id FROM payments") == [(COMPLETED_RIDE,)]
    command.check(config)
