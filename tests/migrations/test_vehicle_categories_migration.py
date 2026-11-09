import sqlite3
import uuid
from pathlib import Path

from alembic import command

from taxi_service.database.migrations import alembic_config

BEFORE = "c6f8a4d219e0"
REVISION = "a3267d91e0b4"
CATEGORIES = ["economy", "comfort", "comfort_plus", "business"]


def test_upgrade_preserves_every_legacy_category_and_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "categories.db"
    config = alembic_config(f"sqlite+aiosqlite:///{path}", configure_logging=False)
    command.upgrade(config, BEFORE)
    vehicles = []
    with sqlite3.connect(path) as db:
        for category in CATEGORIES:
            user_id, vehicle_id = uuid.uuid4().hex, uuid.uuid4().hex
            vehicles.append(vehicle_id)
            db.execute(
                "INSERT INTO users (id, username, username_normalized, "
                "password_hash, role, created_at) "
                "VALUES (?, ?, ?, 'hash', 'driver', '2026-11-09 09:00:00')",
                (user_id, category, category),
            )
            db.execute(
                "INSERT INTO driver_profiles (user_id, approval_status, is_online, "
                "created_at, updated_at) "
                "VALUES (?, 'pending', 0, '2026-11-09 09:00:00', '2026-11-09 09:00:00')",
                (user_id,),
            )
            db.execute(
                "INSERT INTO vehicles (id, driver_id, make, model, color, plate_number, "
                "year, car_class, updated_at) "
                "VALUES (?, ?, 'Toyota', 'Camry', 'white', ?, 2020, ?, '2026-11-09 09:00:00')",
                (vehicle_id, user_id, f"{len(vehicles):03d}TEST", category),
            )
    command.upgrade(config, REVISION)
    with sqlite3.connect(path) as db:
        for i, vehicle_id in enumerate(vehicles):
            rows = db.execute(
                "SELECT tariff FROM vehicle_categories WHERE vehicle_id = ?", (vehicle_id,)
            ).fetchall()
            assert {row[0] for row in rows} == set(CATEGORIES[: i + 1])
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    command.downgrade(config, BEFORE)
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM vehicles").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM vehicle_categories").fetchone()[0] == 10
