"""Load the demonstration data into the configured database (local command).

Usage::

    uv run python scripts/seed.py [--refresh-locations]

Creates the missing demo accounts (``taxi_service.seeds.demo``): demo_admin,
demo_passenger_1..2 and demo_driver_1..3, approved and online near central
Almaty. Existing demo accounts are skipped and never changed; nothing is
deleted. ``--refresh-locations`` additionally re-stamps the location of the
existing demo drivers and puts them online (a location counts for 60 s).

The database comes from DATABASE_URL (environment or ``.env``); it must be an
existing SQLite file migrated to head (``uv run alembic upgrade head``). The
password of created accounts is DEMO_PASSWORD (environment or ``.env``),
otherwise asked twice without echo; it is needed only when something is
created and is never printed.

Exit codes: 0 done, 1 environment or database not suitable, 2 invalid input.
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from pydantic import SecretStr, TypeAdapter, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from taxi_service.core.clock import SystemClock
from taxi_service.core.config import Settings
from taxi_service.database.migrations import expected_heads
from taxi_service.database.readiness import DatabaseReadiness, check_database
from taxi_service.database.session import create_database_engine, create_session_factory
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.schemas import NewPassword
from taxi_service.seeds.demo import (
    DemoPlan,
    DemoSeedConflictError,
    SeedReport,
    apply_demo_seed,
    plan_demo_seed,
)

PASSWORD_VARIABLE = "DEMO_PASSWORD"
NOT_READY = "database is missing or not migrated; run: uv run alembic upgrade head"
NOT_SQLITE_FILE = "the demo seed needs a SQLite database file in DATABASE_URL"

_PASSWORD = TypeAdapter[SecretStr](NewPassword)


class InputError(Exception):
    """Invalid command input; the message never contains the password."""


class DatabaseNotReadyError(Exception):
    pass


class _SeedEnvironment(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    demo_password: SecretStr | None = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the demonstration data.")
    parser.add_argument(
        "--refresh-locations",
        action="store_true",
        help="also re-stamp the locations of existing demo drivers and put them online",
    )
    args = parser.parse_args(argv)
    try:
        settings = Settings()
    except ValidationError:
        return _fail("DATABASE_URL is missing or not a database URL")
    url = make_url(settings.database_url)
    if not _is_sqlite_file(url):
        return _fail(NOT_SQLITE_FILE)
    try:
        configured_password = _configured_password()
        plan = asyncio.run(_plan(settings))
        password = configured_password
        if plan.missing and password is None:
            password = _prompted_password()
        report = asyncio.run(_apply(settings, plan, password, args.refresh_locations))
    except InputError as error:
        return _fail(str(error), exit_code=2)
    except (DatabaseNotReadyError, OperationalError):
        return _fail(NOT_READY)
    except DemoSeedConflictError as error:
        return _fail(f"{error}; nothing changed")
    except UsernameTakenError:
        return _fail("a demo account was created meanwhile; run the seed again")
    _print_report(url, report)
    return 0


async def _plan(settings: Settings) -> DemoPlan:
    engine = create_database_engine(settings.database_url)
    try:
        if await check_database(engine, expected_heads()) is not DatabaseReadiness.READY:
            raise DatabaseNotReadyError
        return await plan_demo_seed(create_session_factory(engine))
    finally:
        await engine.dispose()


async def _apply(
    settings: Settings, plan: DemoPlan, password: str | None, refresh_locations: bool
) -> SeedReport:
    engine = create_database_engine(settings.database_url)
    try:
        return await apply_demo_seed(
            create_session_factory(engine),
            plan,
            clock=SystemClock(),
            hasher=PasswordHasher.from_settings(settings),
            password=password,
            refresh_locations=refresh_locations,
        )
    finally:
        await engine.dispose()


def _is_sqlite_file(url: URL) -> bool:
    return url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:")


def _configured_password() -> str | None:
    """DEMO_PASSWORD from the environment or ``.env``, validated; empty counts as unset."""
    configured = _SeedEnvironment().demo_password
    if configured is None or not configured.get_secret_value():
        return None
    return _validated_password(configured.get_secret_value())


def _prompted_password() -> str:
    if not sys.stdin.isatty():
        raise InputError(f"set {PASSWORD_VARIABLE}: there is no terminal to ask for the password")
    password = getpass.getpass("Password for the demo accounts: ")
    if getpass.getpass("Repeat password: ") != password:
        raise InputError("passwords do not match")
    return _validated_password(password)


def _validated_password(value: str) -> str:
    try:
        return _PASSWORD.validate_python(value).get_secret_value()
    except ValidationError:
        raise InputError("password must be 10-128 characters") from None


def _print_report(url: URL, report: SeedReport) -> None:
    print(f"Demo seed: {Path(url.database or '').name}")
    for entry in report.entries:
        line = f"  {entry.action:<9} {entry.role.value:<9} {entry.username:<16} {entry.detail}"
        print(line.rstrip())
    print(
        f"Summary: {report.count('created')} created, {report.count('skipped')} skipped,"
        f" {report.count('refreshed')} refreshed"
    )
    print("Driver locations stay fresh for 60 s; before a demo run again with --refresh-locations.")


def _fail(message: str, *, exit_code: int = 1) -> int:
    print(f"error: {message}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
