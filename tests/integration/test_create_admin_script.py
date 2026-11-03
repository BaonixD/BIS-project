"""scripts/create_admin.py, run as a real process against this test's database.

The working directory is the temporary directory, so no developer ``.env`` is
read; the password comes from ADMIN_PASSWORD and hashing uses minimal cost.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import select

from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.users.models import User, UserRole

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "create_admin.py"
ADMIN_PASSWORD = "Adm1n-only-passphrase"


@dataclass(frozen=True)
class ScriptRunner:
    database_url: str
    cwd: Path

    def __call__(
        self, *args: str, password: str | None = ADMIN_PASSWORD, database_url: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DATABASE_URL", "ADMIN_PASSWORD"}
        }
        env |= {
            "DATABASE_URL": database_url or self.database_url,
            "PASSWORD_HASH_TIME_COST": "1",
            "PASSWORD_HASH_MEMORY_KIB": "8",
            "PASSWORD_HASH_PARALLELISM": "1",
        }
        if password is not None:
            env["ADMIN_PASSWORD"] = password
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
def run_script(database_url: str, tmp_path: Path) -> ScriptRunner:
    return ScriptRunner(database_url, tmp_path)


async def stored_users(session_factory: SessionFactory) -> list[User]:
    async with session_factory() as session, read_transaction(session):
        return list(await session.scalars(select(User)))


def output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


async def test_creates_admin_with_password_from_environment(
    run_script: ScriptRunner, session_factory: SessionFactory
) -> None:
    result = run_script("--username", "Root_Admin")

    assert result.returncode == 0, output(result)
    assert "Root_Admin" in result.stdout
    assert ADMIN_PASSWORD not in output(result)
    [admin] = await stored_users(session_factory)
    assert (admin.username, admin.role) == ("Root_Admin", UserRole.ADMIN)
    assert admin.password_hash.startswith("$argon2id$")


async def test_existing_username_is_an_error_and_changes_nothing(
    run_script: ScriptRunner, session_factory: SessionFactory
) -> None:
    assert run_script("--username", "root").returncode == 0
    [before] = await stored_users(session_factory)

    result = run_script("--username", "ROOT", password="An0ther-passphrase")

    assert result.returncode == 1
    assert "already exists" in result.stderr
    [after] = await stored_users(session_factory)
    assert after.password_hash == before.password_hash


@pytest.mark.parametrize(
    ("args", "password", "message"),
    [
        (("--username", "no spaces"), ADMIN_PASSWORD, "username"),
        (("--username", "root"), "short", "password"),
    ],
)
async def test_invalid_input_is_rejected_before_touching_the_database(
    run_script: ScriptRunner,
    session_factory: SessionFactory,
    args: tuple[str, ...],
    password: str,
    message: str,
) -> None:
    result = run_script(*args, password=password)

    assert result.returncode == 2
    assert message in result.stderr.lower()
    assert password not in output(result)
    assert await stored_users(session_factory) == []


def test_missing_database_file_is_reported_and_not_created(
    run_script: ScriptRunner, tmp_path: Path
) -> None:
    missing = tmp_path / "missing-test.db"

    result = run_script("--username", "root", database_url=f"sqlite+aiosqlite:///{missing}")

    assert result.returncode == 1
    assert "alembic upgrade head" in result.stderr
    assert not missing.exists()
