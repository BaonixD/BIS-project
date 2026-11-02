"""POST /auth/login and GET /auth/session: cookie session with a server-side expiry."""

import hashlib
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from support.auth import (
    LOGIN_URL,
    SESSION_COOKIE,
    SESSION_URL,
    login,
    register,
    register_and_login,
)
from support.clock import ManualClock
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.models import AuthSession

SESSION_TTL = timedelta(days=7)


def iso(clock: ManualClock, delta: timedelta = timedelta(0)) -> str:
    return (clock.now() + delta).isoformat().replace("+00:00", "Z")


def without_request_id(response: httpx.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    body.pop("request_id")
    return body


@pytest.fixture
async def alice(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await register(client, "Alice", role="driver")
    assert response.status_code == 201
    user: dict[str, Any] = response.json()
    return user


async def test_login_sets_http_only_session_cookie(
    client: httpx.AsyncClient, clock: ManualClock, alice: dict[str, Any]
) -> None:
    response = await login(client, "Alice")

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    token = response.cookies[SESSION_COOKIE]
    assert len(token) >= 43  # 32 random bytes, URL-safe base64
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert {"httponly", "secure", "samesite=lax", "path=/", "max-age=604800"} <= attributes
    body = response.json()
    assert body["user"] == alice
    assert body["expires_at"] == iso(clock, SESSION_TTL)
    assert body["csrf_token"]
    assert token not in response.text


async def test_login_ignores_username_case(
    client: httpx.AsyncClient, alice: dict[str, Any]
) -> None:
    response = await login(client, "aLiCe")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "Alice"


async def test_wrong_password_and_unknown_user_get_the_same_answer(
    client: httpx.AsyncClient, alice: dict[str, Any]
) -> None:
    wrong_password = await login(client, "Alice", password="wrong-password-123")
    unknown_user = await login(client, "Nobody")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert without_request_id(wrong_password) == without_request_id(unknown_user)
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert "set-cookie" not in wrong_password.headers
    assert "set-cookie" not in unknown_user.headers


async def test_session_returns_current_user_and_csrf_token(
    client: httpx.AsyncClient, alice: dict[str, Any]
) -> None:
    logged_in = (await login(client, "Alice")).json()

    response = await client.get(SESSION_URL)

    assert response.status_code == 200
    assert response.json() == logged_in


async def test_session_without_cookie_is_not_authenticated(client: httpx.AsyncClient) -> None:
    response = await client.get(SESSION_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_unknown_session_token_is_not_authenticated(client: httpx.AsyncClient) -> None:
    client.cookies.set(SESSION_COOKIE, "forged-token-value", domain="testserver")

    response = await client.get(SESSION_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_session_expires_after_seven_days_of_server_time(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    await register_and_login(client, "alice")

    clock.advance(SESSION_TTL - timedelta(seconds=1))
    assert (await client.get(SESSION_URL)).status_code == 200

    clock.advance(timedelta(seconds=1))
    response = await client.get(SESSION_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_database_keeps_only_the_hash_of_the_session_token(
    client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    await register(client, "alice")
    token = (await login(client, "alice")).cookies[SESSION_COOKIE]

    async with session_factory() as session, read_transaction(session):
        [stored] = list(await session.scalars(select(AuthSession)))

    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in {stored.token_hash, stored.csrf_token}
    assert stored.created_at == clock.now()
    assert stored.expires_at == clock.now() + SESSION_TTL
    assert stored.revoked_at is None


@pytest.mark.parametrize(
    "body",
    [{"username": "alice"}, {"password": "x" * 10}, {"username": "a", "password": "p" * 129}],
)
async def test_malformed_login_body_is_a_validation_error(
    client: httpx.AsyncClient, body: dict[str, str]
) -> None:
    response = await client.post(LOGIN_URL, json=body)

    assert response.status_code == 422
