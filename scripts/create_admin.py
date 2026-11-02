"""Create an admin account in the configured database (local command).

Usage::

    uv run python scripts/create_admin.py --username NAME

The password is read from the ADMIN_PASSWORD environment variable if set,
otherwise asked twice without echo. It is never printed or stored in plain
text. The database comes from DATABASE_URL (environment or ``.env``) and must
already be migrated (``uv run alembic upgrade head``).

Exit codes: 0 created, 1 username exists or database not ready, 2 invalid input.
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from pydantic import SecretStr, TypeAdapter, ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from taxi_service.core.clock import SystemClock
from taxi_service.core.config import Settings
from taxi_service.database.session import create_database_engine, create_session_factory
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.models import User, UserRole
from taxi_service.modules.users.schemas import NewPassword, Username
from taxi_service.modules.users.service import UserService

PASSWORD_VARIABLE = "ADMIN_PASSWORD"
NOT_READY = "database is missing or not migrated; run: uv run alembic upgrade head"

_USERNAME = TypeAdapter[str](Username)
_PASSWORD = TypeAdapter[SecretStr](NewPassword)


class InputError(Exception):
    """Invalid command input; the message never contains the password."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an admin account.")
    parser.add_argument("--username", required=True, help="3-32 letters, digits or '_'")
    args = parser.parse_args(argv)
    try:
        username = _validated_username(args.username)
        password = _validated_password(_read_password())
    except InputError as error:
        return _fail(str(error), exit_code=2)
    settings = Settings()
    if _sqlite_file_missing(settings.database_url):
        return _fail(NOT_READY)
    try:
        user = asyncio.run(_create_admin(settings, username, password))
    except UsernameTakenError:
        return _fail(f"user {username!r} already exists (in some letter case); nothing changed")
    except OperationalError:
        return _fail(NOT_READY)
    print(f"Created admin {user.username} (id {user.id})")
    return 0


async def _create_admin(settings: Settings, username: str, password: str) -> User:
    engine = create_database_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            service = UserService(session, SystemClock(), PasswordHasher.from_settings(settings))
            return await service.create_user(
                username=username, password=password, role=UserRole.ADMIN
            )
    finally:
        await engine.dispose()


def _validated_username(value: str) -> str:
    try:
        return _USERNAME.validate_python(value)
    except ValidationError:
        raise InputError("username must be 3-32 letters, digits or '_'") from None


def _validated_password(value: str) -> str:
    try:
        return _PASSWORD.validate_python(value).get_secret_value()
    except ValidationError:
        raise InputError("password must be 10-128 characters") from None


def _read_password() -> str:
    from_environment = os.environ.get(PASSWORD_VARIABLE)
    if from_environment is not None:
        return from_environment
    password = getpass.getpass("Admin password: ")
    if getpass.getpass("Repeat password: ") != password:
        raise InputError("passwords do not match")
    return password


def _sqlite_file_missing(database_url: str) -> bool:
    # Connecting would silently create an empty SQLite file.
    url = make_url(database_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or database in (None, "", ":memory:"):
        return False
    return not Path(database).exists()


def _fail(message: str, *, exit_code: int = 1) -> int:
    print(f"error: {message}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
