"""Sign-in with Google for passengers: GET /auth/providers and POST /auth/google.

The Google verifier is replaced by ``support.google.FakeGoogleVerifier`` through
``create_app(google_verifier=...)``; no request leaves the test.
"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from support.auth import (
    CSRF_HEADER,
    PASSWORD,
    SESSION_COOKIE,
    SESSION_URL,
    login,
    register,
    register_and_login,
    use_session_token,
)
from support.clock import ManualClock
from support.google import CLIENT_ID, GOOGLE_URL, PROVIDERS_URL, FakeGoogleVerifier
from support.routing import FakeRoutingProvider
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.main import create_app
from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.users.models import User, UserProfile, UserRole

FRONTEND = "http://localhost:5173"
ME_URL = "/api/v1/users/me"


@pytest.fixture
def client_id() -> str | None:
    return CLIENT_ID


@pytest.fixture
def settings(settings: Settings, client_id: str | None) -> Settings:
    return settings.model_copy(
        update={"google_client_id": client_id, "cors_allowed_origins": [FRONTEND]}
    )


@pytest.fixture
def google() -> FakeGoogleVerifier:
    return FakeGoogleVerifier()


@pytest.fixture
def app(
    settings: Settings,
    clock: ManualClock,
    routing_provider: FakeRoutingProvider,
    payment_settings: PaymentSettings,
    google: FakeGoogleVerifier,
) -> FastAPI:
    return create_app(
        settings,
        clock=clock,
        routing_provider=routing_provider,
        payment_settings=payment_settings,
        google_verifier=google,
    )


async def sign_in(client: httpx.AsyncClient, credential: str) -> httpx.Response:
    return await client.post(
        GOOGLE_URL, json={"credential": credential}, headers={"Origin": FRONTEND}
    )


async def users(session_factory: SessionFactory) -> list[User]:
    async with session_factory() as session, read_transaction(session):
        return list(await session.scalars(select(User).order_by(User.created_at, User.username)))


async def count_sessions(session_factory: SessionFactory) -> int:
    async with session_factory() as session, read_transaction(session):
        return (await session.scalar(select(func.count()).select_from(AuthSession))) or 0


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_providers_expose_the_google_client_id(client: httpx.AsyncClient) -> None:
    response = await client.get(PROVIDERS_URL)

    assert response.status_code == 200
    assert response.json() == {"google_client_id": CLIENT_ID}


@pytest.mark.parametrize("client_id", [None])
async def test_providers_without_client_id_report_google_off(client: httpx.AsyncClient) -> None:
    response = await client.get(PROVIDERS_URL)

    assert response.status_code == 200
    assert response.json() == {"google_client_id": None}


async def test_first_sign_in_creates_a_passenger_with_a_session(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    credential = google.issue("10001", "Alice.Smith@gmail.com", name="Alice Smith")

    response = await sign_in(client, credential)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["role"] == "passenger"
    assert body["user"]["username"] == "alice_smith"
    assert body["csrf_token"]
    attributes = {part.strip().lower() for part in response.headers["set-cookie"].split(";")[1:]}
    assert {"httponly", "secure", "samesite=lax", "path=/"} <= attributes
    assert google.calls == [credential]
    session = (await client.get(SESSION_URL)).json()
    assert session["user"] == body["user"]
    (stored,) = await users(session_factory)
    assert (stored.google_sub, stored.email, stored.password_hash) == (
        "10001",
        "Alice.Smith@gmail.com",
        None,
    )
    assert stored.role is UserRole.PASSENGER


async def test_first_sign_in_takes_the_display_name_from_google(
    client: httpx.AsyncClient, google: FakeGoogleVerifier
) -> None:
    await sign_in(client, google.issue("10001", "alice@gmail.com", name="Alice Smith"))
    csrf = (await client.get(SESSION_URL)).json()["csrf_token"]

    profile = (await client.get(ME_URL)).json()
    updated = await client.patch(
        ME_URL, json={"phone": "+77011234567"}, headers={CSRF_HEADER: csrf}
    )

    assert profile["display_name"] == "Alice Smith"
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Alice Smith"


async def test_sign_in_without_name_leaves_no_profile(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    await sign_in(client, google.issue("10001", "alice@gmail.com"))

    assert (await client.get(ME_URL)).json()["display_name"] is None
    async with session_factory() as session, read_transaction(session):
        assert await session.scalar(select(func.count()).select_from(UserProfile)) == 0


async def test_repeated_sign_in_with_the_same_subject_returns_the_same_user(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    first = await sign_in(client, google.issue("10001", "alice@gmail.com", name="Alice"))
    second = await sign_in(client, google.issue("10001", "alice.new@gmail.com", name="Other"))

    assert second.status_code == 200
    assert second.json()["user"] == first.json()["user"]
    assert second.json()["csrf_token"] != first.json()["csrf_token"]
    assert len(await users(session_factory)) == 1


async def test_sign_in_replaces_the_browsers_previous_session(
    client: httpx.AsyncClient, google: FakeGoogleVerifier
) -> None:
    await register_and_login(client, "bob")
    previous = client.cookies[SESSION_COOKIE]

    await sign_in(client, google.issue("10001", "alice@gmail.com"))

    assert (await client.get(SESSION_URL)).json()["user"]["username"] == "alice"
    use_session_token(client, previous)
    assert (await client.get(SESSION_URL)).status_code == 401


async def test_concurrent_first_sign_ins_create_one_user(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    session_factory: SessionFactory,
    google: FakeGoogleVerifier,
) -> None:
    responses = await asyncio.gather(
        sign_in(client, google.issue("10001", "alice@gmail.com")),
        sign_in(other_client, google.issue("10001", "alice@gmail.com")),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json()["user"] == responses[1].json()["user"]
    assert len(await users(session_factory)) == 1


async def test_username_collision_gets_a_suffix_and_never_links_accounts(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    local = (await register(client, "Alice", role="driver")).json()

    first = await sign_in(client, google.issue("10001", "alice@gmail.com"))
    second = await sign_in(client, google.issue("10002", "alice@yahoo.com"))

    assert first.json()["user"]["username"] == "alice_2"
    assert second.json()["user"]["username"] == "alice_3"
    assert {first.json()["user"]["role"], second.json()["user"]["role"]} == {"passenger"}
    assert local["id"] not in {first.json()["user"]["id"], second.json()["user"]["id"]}
    assert len(await users(session_factory)) == 3


async def test_same_email_with_another_subject_is_another_account(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    first = await sign_in(client, google.issue("10001", "alice@gmail.com"))
    second = await sign_in(client, google.issue("10002", "alice@gmail.com"))

    assert first.json()["user"]["id"] != second.json()["user"]["id"]
    assert len(await users(session_factory)) == 2


@pytest.mark.parametrize("kind", ["unknown", "other_audience"])
async def test_invalid_credential_is_refused(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    google: FakeGoogleVerifier,
    kind: str,
) -> None:
    credential = (
        "not-a-google-token"
        if kind == "unknown"
        else google.issue(
            "10001", "alice@gmail.com", audience="someone-else.apps.googleusercontent.com"
        )
    )

    response = await sign_in(client, credential)

    assert response.status_code == 401
    assert error_code(response) == "invalid_google_token"
    assert "set-cookie" not in response.headers
    assert await users(session_factory) == []


@pytest.mark.parametrize("email", ["alice@gmail.com", None])
async def test_unverified_or_missing_email_is_refused(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    google: FakeGoogleVerifier,
    email: str | None,
) -> None:
    credential = google.issue("10001", email, email_verified=email is None)

    response = await sign_in(client, credential)

    assert response.status_code == 401
    assert error_code(response) == "invalid_google_token"
    assert await users(session_factory) == []


@pytest.mark.parametrize("client_id", [None])
async def test_without_client_id_google_sign_in_is_unavailable(
    client: httpx.AsyncClient, session_factory: SessionFactory, google: FakeGoogleVerifier
) -> None:
    response = await sign_in(client, google.issue("10001", "alice@gmail.com"))

    assert response.status_code == 503
    assert error_code(response) == "google_login_unavailable"
    assert google.calls == []
    assert await users(session_factory) == []


async def test_google_user_cannot_log_in_with_a_password(
    client: httpx.AsyncClient, google: FakeGoogleVerifier
) -> None:
    await sign_in(client, google.issue("10001", "alice@gmail.com"))
    client.cookies.clear()

    for password in (PASSWORD, "!", "x"):
        response = await login(client, "alice", password=password)
        assert response.status_code == 401
        assert error_code(response) == "invalid_credentials"
        assert "set-cookie" not in response.headers


@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
async def test_sign_in_from_a_foreign_origin_is_refused(
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    google: FakeGoogleVerifier,
    origin: str,
) -> None:
    response = await client.post(
        GOOGLE_URL,
        json={"credential": google.issue("10001", "alice@gmail.com")},
        headers={"Origin": origin},
    )

    assert response.status_code == 403
    assert error_code(response) == "origin_not_allowed"
    assert google.calls == []
    assert await count_sessions(session_factory) == 0


async def test_sign_in_without_origin_is_allowed(
    client: httpx.AsyncClient, google: FakeGoogleVerifier
) -> None:
    response = await client.post(
        GOOGLE_URL, json={"credential": google.issue("10001", "alice@gmail.com")}
    )

    assert response.status_code == 200


async def test_sign_ins_of_one_google_account_are_limited(
    client: httpx.AsyncClient, settings: Settings, google: FakeGoogleVerifier
) -> None:
    for _ in range(settings.login_max_attempts):
        assert (await sign_in(client, google.issue("10001", "alice@gmail.com"))).status_code == 200

    limited = await sign_in(client, google.issue("10001", "alice@gmail.com"))
    other_account = await sign_in(client, google.issue("10002", "bob@gmail.com"))

    assert limited.status_code == 429
    assert error_code(limited) == "too_many_attempts"
    assert other_account.status_code == 200


async def test_password_attempts_never_block_a_google_account(
    client: httpx.AsyncClient, settings: Settings, google: FakeGoogleVerifier
) -> None:
    for username in ("10001", "google:10001"):
        for _ in range(settings.login_max_attempts + 1):
            await login(client, username)

    response = await sign_in(client, google.issue("10001", "alice@gmail.com"))

    assert response.status_code == 200


@pytest.mark.parametrize("body", [{}, {"credential": ""}, {"credential": "x" * 5000}])
async def test_malformed_body_is_a_validation_error(
    client: httpx.AsyncClient, google: FakeGoogleVerifier, body: dict[str, str]
) -> None:
    response = await client.post(GOOGLE_URL, json=body)

    assert response.status_code == 422
    assert google.calls == []
