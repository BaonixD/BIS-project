"""Upgrade a database of the accepted T05 schema with real data to head, then use it.

T05 (``640cf8e50671``) is the last schema released before dispatch, lifecycle
and payments; its rides are upgraded across all later revisions at once. The
accounts carry real password hashes, so after the upgrade the application logs
them in and finishes their rides through the API.

Synchronous on purpose: Alembic's env.py runs its own event loop.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from support.auth import PASSWORD
from support.clock import ManualClock
from support.e2e import expect, open_town, pay, ride_command
from support.history import ADMIN_RIDES_URL
from support.lifecycle import commands_of
from support.payments import actions_of, kaspi_off
from support.rides import RIDES_URL
from support.routing import FakeRoutingProvider
from support.rows import GEOMETRY
from taxi_service.core.config import Settings
from taxi_service.database.migrations import alembic_config, expected_heads
from taxi_service.database.session import create_database_engine, create_session_factory
from taxi_service.main import create_app
from taxi_service.modules.auth.passwords import PasswordHasher

T05_HEAD = "640cf8e50671"
T07_HEAD = "b42082a5b952"
ADMIN, PAT, PIA, SAM, DANA = (uuid.UUID(int=n).hex for n in range(1, 6))
COMPLETED, ASSIGNED, SEARCHING = (uuid.UUID(int=n).hex for n in range(11, 14))
SNAPSHOT_COLUMNS = (
    "pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude, distance_m,"
    " duration_s, route_geometry, provider, amount_kzt, currency, tariff_version"
)
TABLES = (
    "users",
    "user_profiles",
    "driver_profiles",
    "vehicles",
    "ride_quotes",
    "rides",
    "idempotency_records",
)
AFTER_UPGRADE = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)  # SEARCHING's window ended at 09:04
RIDE_COLUMNS = "id, status, passenger_id, driver_id, amount_kzt, created_at, updated_at"


@pytest.fixture
def database_file(tmp_path: Path) -> Path:
    return tmp_path / "t05-upgrade.db"


@pytest.fixture
def config(database_file: Path) -> Config:
    return alembic_config(f"sqlite+aiosqlite:///{database_file}", configure_logging=False)


@pytest.fixture
def test_settings(database_file: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{database_file}",
        password_hash_time_cost=1,
        password_hash_memory_kib=8,
        password_hash_parallelism=1,
    )


def execute(config: Config, *statements: str) -> list[tuple[object, ...]]:
    """Run the statements in one transaction; the rows of the last one."""

    async def run() -> list[tuple[object, ...]]:
        engine = create_database_engine(config.attributes["database_url"])
        try:
            async with engine.begin() as connection:
                rows: list[tuple[object, ...]] = []
                for statement in statements:
                    result = await connection.execute(text(statement))
                    rows = [tuple(row) for row in result] if result.returns_rows else []
                return rows
        finally:
            await engine.dispose()

    return asyncio.run(run())


def counts(config: Config) -> dict[str, object]:
    return {table: execute(config, f"SELECT count(*) FROM {table}")[0][0] for table in TABLES}


def user(user_id: str, name: str, role: str, password_hash: str) -> str:
    return (
        "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
        f" VALUES ('{user_id}', '{name}', '{name}', '{password_hash}', '{role}',"
        " '2026-11-03 08:00:00.000000')"
    )


def ride(ride_id: str, passenger: str, driver: str | None, status: str, amount: int) -> list[str]:
    quote_id = ride_id[::-1]
    snapshot = f"76.9572, 43.2389, 76.9286, 43.2187, 10000, 1500, '{GEOMETRY}', 'fake', {amount},"
    snapshot += " 'KZT', 'edu-v1'"
    driver_value = f"'{driver}'" if driver else "NULL"
    return [
        f"INSERT INTO ride_quotes (id, passenger_id, created_at, expires_at, {SNAPSHOT_COLUMNS})"
        f" VALUES ('{quote_id}', '{passenger}', '2026-11-03 09:00:00.000000',"
        f" '2026-11-03 09:05:00.000000', {snapshot})",
        f"INSERT INTO rides (id, passenger_id, driver_id, quote_id, status, created_at,"
        f" updated_at, {SNAPSHOT_COLUMNS}) VALUES ('{ride_id}', '{passenger}', {driver_value},"
        f" '{quote_id}', '{status}', '2026-11-03 09:01:00.000000',"
        f" '2026-11-03 09:31:00.000000', {snapshot})",
    ]


def fill_t05_database(config: Config, settings: Settings) -> None:
    password_hash = asyncio.run(PasswordHasher.from_settings(settings).hash(PASSWORD))
    execute(
        config,
        user(ADMIN, "admin", "admin", password_hash),
        user(PAT, "pat", "passenger", password_hash),
        user(PIA, "pia", "passenger", password_hash),
        user(SAM, "sam", "passenger", password_hash),
        user(DANA, "dana", "driver", password_hash),
        "INSERT INTO user_profiles (user_id, display_name, phone, updated_at)"
        f" VALUES ('{PAT}', 'Pat', NULL, '2026-11-03 08:00:00.000000')",
        "INSERT INTO driver_profiles (user_id, full_name, phone, license_number,"
        " approval_status, approved_at, approved_by, is_online, longitude, latitude,"
        " location_updated_at, created_at, updated_at) VALUES"
        f" ('{DANA}', 'Dana Driver', '+77011234567', 'KZ1234567', 'approved',"
        f" '2026-11-03 08:10:00.000000', '{ADMIN}', 1, 76.9580, 43.2389,"
        " '2026-11-03 09:00:00.000000', '2026-11-03 08:00:00.000000',"
        " '2026-11-03 08:10:00.000000')",
        "INSERT INTO vehicles (id, driver_id, make, model, color, plate_number, year, updated_at)"
        f" VALUES ('{uuid.UUID(int=21).hex}', '{DANA}', 'Toyota', 'Camry', 'white', '123ABC02',"
        " 2020, '2026-11-03 08:00:00.000000')",
        *ride(COMPLETED, PAT, DANA, "completed", 2200),
        *ride(ASSIGNED, PIA, DANA, "assigned", 1500),
        *ride(SEARCHING, SAM, None, "searching", 1800),
        "INSERT INTO idempotency_records (id, user_id, operation, key, request_fingerprint,"
        f" resource_id, created_at) VALUES ('{uuid.UUID(int=31).hex}', '{PIA}', 'create_ride',"
        f" 'key-1', '{'0' * 64}', '{ASSIGNED}', '2026-11-03 09:01:00.000000')",
    )


@pytest.fixture
def t05_database(config: Config, test_settings: Settings) -> dict[str, object]:
    """A database at T05 with rides; the row counts before the upgrade."""
    command.upgrade(config, T05_HEAD)
    fill_t05_database(config, test_settings)
    return counts(config)


def test_t05_data_survives_the_upgrade_and_completed_rides_get_payments(
    config: Config, t05_database: dict[str, object]
) -> None:
    rides_before = execute(config, f"SELECT {RIDE_COLUMNS} FROM rides ORDER BY id")

    command.upgrade(config, "head")

    assert execute(config, "SELECT version_num FROM alembic_version") == [
        (head,) for head in expected_heads()
    ]
    command.check(config)
    assert counts(config) == t05_database
    assert execute(config, f"SELECT {RIDE_COLUMNS} FROM rides ORDER BY id") == rides_before
    assert (
        execute(
            config,
            "SELECT search_started_at, search_deadline, assigned_at, completed_at FROM rides",
        )
        == [("2026-11-03 09:01:00.000000", "2026-11-03 09:04:00.000000", None, None)] * 3
    )
    # Backfill: the completed ride (and only it) gets unpaid cash, opened at updated_at.
    assert execute(
        config,
        "SELECT ride_id, amount_kzt, method, status, verification, created_at FROM payments",
    ) == [(COMPLETED, 2200, "cash", "unpaid", "manual", "2026-11-03 09:31:00.000000")]
    assert execute(config, "SELECT action, to_status, actor_id FROM payment_events") == [
        ("open", "unpaid", None)
    ]
    assert execute(config, "SELECT count(*) FROM ride_offers")[0][0] == 0
    assert execute(config, "SELECT count(*) FROM ride_events")[0][0] == 0


def test_downgrade_one_step_and_back_keeps_t05_data(
    config: Config, t05_database: dict[str, object]
) -> None:
    command.upgrade(config, "head")

    command.downgrade(config, "-1")

    assert execute(config, "SELECT version_num FROM alembic_version") == [(T07_HEAD,)]
    assert execute(config, "SELECT name FROM sqlite_master WHERE name = 'payments'") == []
    assert counts(config) == t05_database

    command.upgrade(config, "head")

    command.check(config)
    assert counts(config) == t05_database
    assert execute(config, "SELECT ride_id, status FROM payments") == [(COMPLETED, "unpaid")]


def test_upgraded_rides_are_finished_and_paid_through_the_api(
    config: Config, t05_database: dict[str, object], test_settings: Settings
) -> None:
    command.upgrade(config, "head")
    asyncio.run(finish_upgraded_rides(test_settings))


async def finish_upgraded_rides(settings: Settings) -> None:
    clock = ManualClock(AFTER_UPGRADE)
    app = create_app(
        settings, clock=clock, routing_provider=FakeRoutingProvider(), payment_settings=kaspi_off()
    )
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with open_town(app, session_factory, clock) as town:
            dana = await town.login("dana")
            pat = await town.login("pat")
            admin = await town.login("admin")
            history = expect(await dana.get(RIDES_URL))["items"]
            # Same created_at: the larger id comes first.
            assert [(item["id"], item["status"], item["payment_status"]) for item in history] == [
                (str(uuid.UUID(ASSIGNED)), "assigned", None),
                (str(uuid.UUID(COMPLETED)), "completed", "unpaid"),
            ]

            for command_name in ("arrive", "start", "complete"):
                expect(await ride_command(dana, str(uuid.UUID(ASSIGNED)), command_name))
            confirmed = expect(await pay(dana, str(uuid.UUID(COMPLETED)), "confirm"))
            assert (confirmed["status"], confirmed["amount_kzt"]) == ("confirmed", 2200)
            opened = expect(await dana.get(f"{RIDES_URL}/{uuid.UUID(ASSIGNED)}/payment"))
            assert (opened["status"], opened["amount_kzt"]) == ("unpaid", 1500)
            [paid] = expect(await pat.get(RIDES_URL))["items"]
            assert (paid["status"], paid["payment_status"]) == ("completed", "confirmed")

            assert await town.dispatch_step() == 1  # SEARCHING's search ended long ago
            statuses = {
                item["id"]: item["status"]
                for item in expect(await admin.get(ADMIN_RIDES_URL))["items"]
            }
            assert statuses == {
                str(uuid.UUID(COMPLETED)): "completed",
                str(uuid.UUID(ASSIGNED)): "completed",
                str(uuid.UUID(SEARCHING)): "no_driver",
            }
        assert await actions_of(session_factory, uuid.UUID(COMPLETED)) == ["open", "confirm"]
        assert await actions_of(session_factory, uuid.UUID(ASSIGNED)) == ["open"]
        assert await commands_of(session_factory, uuid.UUID(SEARCHING)) == ["mark_no_driver"]
    finally:
        await engine.dispose()
