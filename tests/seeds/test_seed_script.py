"""scripts/seed.py, run as a real process against this test's database.

The working directory is the temporary directory, so no developer ``.env`` is
read; the password comes from DEMO_PASSWORD and hashing uses minimal cost.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import select

from taxi_service.core.clock import SystemClock
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import User, UserRole
from taxi_service.seeds.demo import DEMO_USERNAMES

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
DEMO_PASSWORD = "Dem0-only-passphrase"


@dataclass(frozen=True)
class SeedRunner:
    database_url: str
    cwd: Path

    def __call__(
        self, *args: str, password: str | None = DEMO_PASSWORD, database_url: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DATABASE_URL", "DEMO_PASSWORD"}
        }
        env |= {
            "DATABASE_URL": database_url or self.database_url,
            "PASSWORD_HASH_TIME_COST": "1",
            "PASSWORD_HASH_MEMORY_KIB": "8",
            "PASSWORD_HASH_PARALLELISM": "1",
        }
        if password is not None:
            env["DEMO_PASSWORD"] = password
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.cwd,
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )


@pytest.fixture
def run_seed(database_url: str, tmp_path: Path) -> SeedRunner:
    return SeedRunner(database_url, tmp_path)


async def stored_users(session_factory: SessionFactory) -> dict[str, User]:
    async with session_factory() as session, read_transaction(session):
        return {user.username: user for user in await session.scalars(select(User))}


def output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


async def test_first_run_creates_the_demo_data_and_prints_a_summary(
    run_seed: SeedRunner, session_factory: SessionFactory
) -> None:
    result = run_seed()

    assert result.returncode == 0, output(result)
    assert "6 created, 0 skipped" in result.stdout
    assert all(name in result.stdout for name in DEMO_USERNAMES)
    assert DEMO_PASSWORD not in output(result)
    users = await stored_users(session_factory)
    assert sorted(users) == sorted(DEMO_USERNAMES)
    assert users["demo_admin"].role is UserRole.ADMIN


async def test_second_run_skips_everything_and_needs_no_password(
    run_seed: SeedRunner, session_factory: SessionFactory
) -> None:
    assert run_seed().returncode == 0
    before = {
        name: user.password_hash for name, user in (await stored_users(session_factory)).items()
    }

    result = run_seed(password=None)

    assert result.returncode == 0, output(result)
    assert "0 created, 6 skipped" in result.stdout
    after = {
        name: user.password_hash for name, user in (await stored_users(session_factory)).items()
    }
    assert after == before


def test_refresh_locations_reports_the_refreshed_drivers(run_seed: SeedRunner) -> None:
    assert run_seed().returncode == 0

    result = run_seed("--refresh-locations", password=None)

    assert result.returncode == 0, output(result)
    assert "3 refreshed" in result.stdout


async def test_password_is_read_from_a_dotenv_file_in_the_working_directory(
    run_seed: SeedRunner, session_factory: SessionFactory, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(f"DEMO_PASSWORD={DEMO_PASSWORD}\n", encoding="utf-8")

    result = run_seed(password=None)

    assert result.returncode == 0, output(result)
    assert DEMO_PASSWORD not in output(result)
    assert len(await stored_users(session_factory)) == len(DEMO_USERNAMES)


@pytest.mark.parametrize("password", ["short-pw", "x" * 129])
async def test_invalid_password_is_rejected_before_anything_is_created(
    run_seed: SeedRunner, session_factory: SessionFactory, password: str
) -> None:
    result = run_seed(password=password)

    assert result.returncode == 2
    assert "password" in result.stderr.lower()
    assert password not in output(result)
    assert await stored_users(session_factory) == {}


async def test_missing_password_without_a_terminal_is_an_input_error(
    run_seed: SeedRunner, session_factory: SessionFactory
) -> None:
    result = run_seed(password=None)

    assert result.returncode == 2
    assert "DEMO_PASSWORD" in result.stderr
    assert await stored_users(session_factory) == {}


def test_missing_database_file_is_reported_and_not_created(
    run_seed: SeedRunner, tmp_path: Path
) -> None:
    missing = tmp_path / "missing-test.db"

    result = run_seed(database_url=f"sqlite+aiosqlite:///{missing}")

    assert result.returncode == 1
    assert "alembic upgrade head" in result.stderr
    assert not missing.exists()


def test_unmigrated_database_is_reported(run_seed: SeedRunner, empty_database_url: str) -> None:
    result = run_seed(database_url=empty_database_url)

    assert result.returncode == 1
    assert "alembic upgrade head" in result.stderr


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://demo@localhost/taxi",
        "sqlite+aiosqlite://",
        "sqlite+aiosqlite:///:memory:",
    ],
)
def test_only_a_sqlite_file_is_accepted(run_seed: SeedRunner, database_url: str) -> None:
    result = run_seed(database_url=database_url)

    assert result.returncode == 1
    assert "SQLite database file" in result.stderr
    assert "localhost" not in output(result)


async def test_conflicting_existing_account_is_reported_and_nothing_changes(
    run_seed: SeedRunner, session_factory: SessionFactory, settings: Settings
) -> None:
    async with session_factory() as session:
        await users_service.create_user(
            session,
            "demo_admin",
            "passenger-passphrase",
            UserRole.PASSENGER,
            clock=SystemClock(),
            hasher=PasswordHasher.from_settings(settings),
        )

    result = run_seed()

    assert result.returncode == 1
    assert "demo_admin" in result.stderr
    assert "nothing changed" in result.stderr
    assert list(await stored_users(session_factory)) == ["demo_admin"]
