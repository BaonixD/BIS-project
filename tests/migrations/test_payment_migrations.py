"""Payment revisions on a database with rides.

T08B (``272671ab4753``) opens an unpaid cash payment for every completed ride;
the simple-payments revision folds ``reported``/``confirmed`` into ``paid``.
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

T07_HEAD = "b42082a5b952"
T08B_HEAD = "272671ab4753"
USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
DRIVER = "3f1e2d3c4b5a69788796a5b4c3d2e1f0"
COMPLETED_RIDE = "2f1e2d3c4b5a69788796a5b4c3d2e1f0"
CANCELLED_RIDE = "4f1e2d3c4b5a69788796a5b4c3d2e1f0"
COMPLETED_AT = "2026-11-03 09:30:00.000000"
UPDATED_AT = "2026-11-03 09:31:00.000000"
SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
REPORTED_RIDE = "5f1e2d3c4b5a69788796a5b4c3d2e1f0"
CONFIRMED_KASPI_RIDE = "6f1e2d3c4b5a69788796a5b4c3d2e1f0"
CONFIRMED_CASH_RIDE = "7f1e2d3c4b5a69788796a5b4c3d2e1f0"
REPORTED_AT = "2026-11-03 09:40:00.000000"
CONFIRMED_AT = "2026-11-03 09:45:00.000000"
PAYMENT_COLUMNS = {
    "id",
    "ride_id",
    "amount_kzt",
    "currency",
    "method",
    "status",
    "paid_at",
    "created_at",
    "updated_at",
}
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


def insert_ride(
    config: Config,
    ride_id: str,
    *,
    status: str,
    amount_kzt: int,
    completed_at: str | None = COMPLETED_AT,
) -> None:
    quote_id = ride_id[::-1]
    snapshot = f"76.95, 43.23, 76.92, 43.21, 10000, 1500, '{{}}', 'fake', {amount_kzt}, 'KZT', 'v1'"
    execute(
        config,
        f"INSERT INTO ride_quotes (id, passenger_id, created_at, expires_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{quote_id}', '{USER}', '2026-11-03 09:00:00.000000',"
        f" '2026-11-03 09:05:00.000000', {snapshot})",
    )
    completed = f"'{completed_at}'" if status == "completed" and completed_at else "NULL"
    execute(
        config,
        "INSERT INTO rides (id, passenger_id, driver_id, quote_id, status, created_at,"
        f" updated_at, search_started_at, search_deadline, completed_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{ride_id}', '{USER}', '{DRIVER}', '{quote_id}', '{status}',"
        f" '2026-11-03 09:01:00.000000', '{UPDATED_AT}',"
        " '2026-11-03 09:01:00.000000', '2026-11-03 09:04:00.000000',"
        f" {completed}, {snapshot})",
    )


def insert_t07_people(config: Config) -> None:
    insert_user(config, USER, "pat", "passenger")
    insert_user(config, DRIVER, "dana", "driver")
    execute(
        config,
        "INSERT INTO driver_profiles (user_id, approval_status, is_online, created_at, updated_at)"
        f" VALUES ('{DRIVER}', 'pending', 0, '2026-11-03 09:00:00.000000',"
        " '2026-11-03 09:00:00.000000')",
    )


def insert_t07_rides(config: Config) -> None:
    insert_t07_people(config)
    insert_ride(config, COMPLETED_RIDE, status="completed", amount_kzt=3100)
    insert_ride(config, CANCELLED_RIDE, status="cancelled", amount_kzt=2200)


def test_completed_rides_get_an_unpaid_cash_payment(config: Config) -> None:
    command.upgrade(config, T07_HEAD)
    insert_t07_rides(config)

    command.upgrade(config, T08B_HEAD)

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


def test_completed_ride_without_completion_time_is_opened_at_its_last_update(
    config: Config,
) -> None:
    # No CHECK ties completed_at to the status, so a completed ride may lack it.
    command.upgrade(config, T07_HEAD)
    insert_t07_people(config)
    insert_ride(config, COMPLETED_RIDE, status="completed", amount_kzt=3100, completed_at=None)

    command.upgrade(config, T08B_HEAD)

    assert execute(config, "SELECT ride_id, status, created_at, updated_at FROM payments") == [
        (COMPLETED_RIDE, "unpaid", UPDATED_AT, UPDATED_AT)
    ]
    assert execute(config, "SELECT action, created_at FROM payment_events") == [
        ("open", UPDATED_AT)
    ]


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
    assert execute(config, "SELECT ride_id, status FROM payments") == [(COMPLETED_RIDE, "unpaid")]
    command.check(config)


def insert_t08b_payments(config: Config) -> None:
    """One payment in each T08B state: unpaid cash, reported and confirmed Kaspi, confirmed cash."""
    command.upgrade(config, T07_HEAD)
    insert_t07_people(config)
    for ride_id in (COMPLETED_RIDE, REPORTED_RIDE, CONFIRMED_KASPI_RIDE, CONFIRMED_CASH_RIDE):
        insert_ride(config, ride_id, status="completed", amount_kzt=3100)
    command.upgrade(config, T08B_HEAD)
    execute(
        config,
        f"UPDATE payments SET method = 'kaspi_link', status = 'reported',"
        f" reported_at = '{REPORTED_AT}' WHERE ride_id = '{REPORTED_RIDE}'",
    )
    execute(
        config,
        f"UPDATE payments SET method = 'kaspi_link', status = 'confirmed',"
        f" reported_at = '{REPORTED_AT}', confirmed_at = '{CONFIRMED_AT}',"
        f" confirmed_by = '{USER}', confirmation_reference = 'POS 1'"
        f" WHERE ride_id = '{CONFIRMED_KASPI_RIDE}'",
    )
    execute(
        config,
        f"UPDATE payments SET status = 'confirmed', confirmed_at = '{CONFIRMED_AT}',"
        f" confirmed_by = '{DRIVER}' WHERE ride_id = '{CONFIRMED_CASH_RIDE}'",
    )


def payment_columns(config: Config) -> set[object]:
    return {row[1] for row in execute(config, "PRAGMA table_info(payments)")}


def test_reported_and_confirmed_payments_become_paid(config: Config) -> None:
    insert_t08b_payments(config)

    command.upgrade(config, "head")

    assert payment_columns(config) == PAYMENT_COLUMNS
    assert execute(
        config,
        "SELECT ride_id, amount_kzt, method, status, paid_at, created_at FROM payments"
        " ORDER BY ride_id",
    ) == [
        (COMPLETED_RIDE, 3100, "cash", "unpaid", None, COMPLETED_AT),
        (REPORTED_RIDE, 3100, "kaspi_link", "paid", REPORTED_AT, COMPLETED_AT),
        (CONFIRMED_KASPI_RIDE, 3100, "kaspi_link", "paid", CONFIRMED_AT, COMPLETED_AT),
        (CONFIRMED_CASH_RIDE, 3100, "cash", "paid", CONFIRMED_AT, COMPLETED_AT),
    ]
    assert execute(config, PAYMENT_TABLES) == [("payments",)]
    command.check(config)


def test_paid_requires_paid_at_after_the_upgrade(config: Config) -> None:
    insert_t08b_payments(config)
    command.upgrade(config, "head")

    for values in ("status = 'paid'", f"paid_at = '{CONFIRMED_AT}'", "status = 'confirmed'"):
        with pytest.raises(IntegrityError, match="CHECK"):
            execute(config, f"UPDATE payments SET {values} WHERE ride_id = '{COMPLETED_RIDE}'")


def test_downgrade_to_t08b_restores_the_manual_schema_as_unpaid(config: Config) -> None:
    insert_t08b_payments(config)
    command.upgrade(config, "head")

    command.downgrade(config, T08B_HEAD)

    assert execute(
        config,
        "SELECT ride_id, method, status, verification, reported_at, confirmed_at,"
        " confirmed_by, confirmation_reference FROM payments ORDER BY ride_id",
    ) == [
        (COMPLETED_RIDE, "cash", "unpaid", "manual", None, None, None, None),
        (REPORTED_RIDE, "kaspi_link", "unpaid", "manual", None, None, None, None),
        (CONFIRMED_KASPI_RIDE, "kaspi_link", "unpaid", "manual", None, None, None, None),
        (CONFIRMED_CASH_RIDE, "cash", "unpaid", "manual", None, None, None, None),
    ]
    assert execute(
        config,
        "SELECT p.ride_id, e.action, e.to_status, e.to_method, e.created_at"
        " FROM payment_events e JOIN payments p ON p.id = e.payment_id ORDER BY p.ride_id",
    ) == [
        (COMPLETED_RIDE, "open", "unpaid", "cash", COMPLETED_AT),
        (REPORTED_RIDE, "open", "unpaid", "kaspi_link", COMPLETED_AT),
        (CONFIRMED_KASPI_RIDE, "open", "unpaid", "kaspi_link", COMPLETED_AT),
        (CONFIRMED_CASH_RIDE, "open", "unpaid", "cash", COMPLETED_AT),
    ]
    with pytest.raises(IntegrityError, match="CHECK"):
        execute(config, f"UPDATE payments SET status = 'paid' WHERE ride_id = '{COMPLETED_RIDE}'")

    command.upgrade(config, "head")

    assert execute(config, "SELECT count(*) FROM payments WHERE status = 'unpaid'") == [(4,)]
    command.check(config)
