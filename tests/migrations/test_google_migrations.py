"""Google sign-in revision of ``users`` on a database with local accounts.

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

GOOGLE_REVISION = "a7c41e9d3b58"
BEFORE_GOOGLE = f"{GOOGLE_REVISION}-1"
LOCAL_USER = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
GOOGLE_USER = "1f1e2d3c4b5a69788796a5b4c3d2e1f0"
SESSION = "5f1e2d3c4b5a69788796a5b4c3d2e1f0"
CREATED_AT = "2026-11-03 09:00:00.000000"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'google-migrations.db'}", configure_logging=False
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


def user_columns(config: Config) -> set[str]:
    return {str(row[1]) for row in execute(config, "PRAGMA table_info(users)")}


def insert_google_user(config: Config, user_id: str, username: str, google_sub: str | None) -> None:
    sub = "NULL" if google_sub is None else f"'{google_sub}'"
    execute(
        config,
        "INSERT INTO users (id, username, username_normalized, password_hash, google_sub, email,"
        f" role, created_at) VALUES ('{user_id}', '{username}', '{username.lower()}', NULL, {sub},"
        f" '{username}@gmail.com', 'passenger', '{CREATED_AT}')",
    )


@pytest.fixture
def local_account(config: Config) -> Config:
    command.upgrade(config, BEFORE_GOOGLE)
    execute(
        config,
        "INSERT INTO users (id, username, username_normalized, password_hash, role, created_at)"
        f" VALUES ('{LOCAL_USER}', 'Pat', 'pat', '$argon2id$hash', 'driver', '{CREATED_AT}')",
    )
    execute(
        config,
        "INSERT INTO auth_sessions (id, user_id, token_hash, csrf_token, created_at, expires_at)"
        f" VALUES ('{SESSION}', '{LOCAL_USER}', 'token-hash', 'csrf', '{CREATED_AT}',"
        " '2026-11-10 09:00:00.000000')",
    )
    return config


def test_upgrade_keeps_local_accounts_and_their_sessions(local_account: Config) -> None:
    command.upgrade(local_account, GOOGLE_REVISION)

    assert {"google_sub", "email"} <= user_columns(local_account)
    assert execute(
        local_account,
        "SELECT username, password_hash, role, google_sub, email FROM users",
    ) == [("Pat", "$argon2id$hash", "driver", None, None)]
    # The batch rebuild of users must not cascade-delete auth_sessions.
    assert execute(local_account, "SELECT token_hash FROM auth_sessions") == [("token-hash",)]


def test_upgraded_users_accept_google_accounts_and_keep_constraints(
    local_account: Config,
) -> None:
    command.upgrade(local_account, GOOGLE_REVISION)

    insert_google_user(local_account, GOOGLE_USER, "alice", "10001")

    with pytest.raises(IntegrityError, match="UNIQUE"):
        insert_google_user(local_account, "2f1e2d3c4b5a69788796a5b4c3d2e1f0", "bob", "10001")
    with pytest.raises(IntegrityError, match="CHECK"):
        insert_google_user(local_account, "3f1e2d3c4b5a69788796a5b4c3d2e1f0", "carl", None)
    with pytest.raises(IntegrityError, match="UNIQUE"):
        insert_google_user(local_account, "4f1e2d3c4b5a69788796a5b4c3d2e1f0", "PAT", "10002")


def test_downgrade_gives_google_accounts_an_unusable_password(local_account: Config) -> None:
    command.upgrade(local_account, GOOGLE_REVISION)
    insert_google_user(local_account, GOOGLE_USER, "alice", "10001")

    command.downgrade(local_account, BEFORE_GOOGLE)

    assert not {"google_sub", "email"} & user_columns(local_account)
    assert execute(
        local_account, "SELECT username, password_hash FROM users ORDER BY username"
    ) == [
        ("Pat", "$argon2id$hash"),
        ("alice", "!"),
    ]
    with pytest.raises(IntegrityError, match="NOT NULL"):
        execute(
            local_account,
            "INSERT INTO users (id, username, username_normalized, password_hash, role,"
            f" created_at) VALUES ('{GOOGLE_USER[::-1]}', 'bob', 'bob', NULL, 'passenger',"
            f" '{CREATED_AT}')",
        )


def test_upgrade_downgrade_upgrade_leaves_no_schema_diff(local_account: Config) -> None:
    command.upgrade(local_account, "head")
    command.downgrade(local_account, BEFORE_GOOGLE)
    command.upgrade(local_account, "head")

    command.check(local_account)
    assert execute(local_account, "SELECT username FROM users") == [("Pat",)]
