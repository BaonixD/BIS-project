"""Passwords and raw session tokens never reach responses, logs or the database file."""

import logging
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import make_url

from support.auth import LOGOUT_URL, SESSION_COOKIE, SESSION_URL, current_session, login, register

PASSWORD = "Sup3r-secret-passphrase"
WRONG_PASSWORD = "Wr0ng-secret-passphrase"
SHORT_PASSWORD = "short-pw1"


@pytest.fixture
def captured_logs(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Everything the app and SQLAlchemy log, SQL statements and parameters included."""
    app_logger = logging.getLogger("taxi_service")  # does not propagate to root
    app_logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="taxi_service")
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")
    yield caplog
    app_logger.removeHandler(caplog.handler)


def database_bytes(database_url: str) -> bytes:
    path = Path(str(make_url(database_url).database))
    files = [path, path.with_name(path.name + "-wal")]
    return b"".join(file.read_bytes() for file in files if file.exists())


async def test_secrets_are_not_exposed(
    client: httpx.AsyncClient, captured_logs: pytest.LogCaptureFixture, database_url: str
) -> None:
    responses = [
        await register(client, "alice", password=SHORT_PASSWORD),
        await register(client, "alice", password=PASSWORD),
        await login(client, "alice", password=WRONG_PASSWORD),
        await login(client, "alice", password=PASSWORD),
    ]
    token = client.cookies[SESSION_COOKIE]
    user = await current_session(client)
    responses += [
        await client.get(SESSION_URL),
        await client.post(LOGOUT_URL, headers=user.csrf_headers),
    ]

    assert [response.status_code for response in responses] == [422, 201, 401, 200, 200, 204]
    secrets = [PASSWORD, WRONG_PASSWORD, SHORT_PASSWORD, token]
    for response in responses:
        exposed = response.text + str(response.headers.get("x-request-id"))
        assert not any(secret in exposed for secret in secrets)
    assert "Login succeeded" in captured_logs.text  # the app logger is really captured
    assert "INSERT INTO auth_sessions" in captured_logs.text  # and SQL with parameters
    assert not any(secret in captured_logs.text for secret in secrets)
    stored = database_bytes(database_url)
    assert not any(secret.encode() in stored for secret in secrets)
    assert b"$argon2id$" in stored
