"""Login and register accept a browser Origin only from the allowlist or the API itself.

Requests without Origin (curl, HTTPX, server-side clients) are allowed: CSRF is a
browser attack, and browsers always send Origin with cross-site POST requests.
"""

import httpx
import pytest
from sqlalchemy import func, select

from support.auth import LOGIN_URL, PASSWORD, REGISTER_URL, register
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.users.models import User

FRONTEND = "http://localhost:5173"
CREDENTIALS = {"username": "alice", "password": PASSWORD}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"cors_allowed_origins": [FRONTEND]})


async def count(session_factory: SessionFactory, model: type[User] | type[AuthSession]) -> int:
    async with session_factory() as session, read_transaction(session):
        return (await session.scalar(select(func.count()).select_from(model))) or 0


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "null", "http://localhost:5174", "http://localhost"]
)
async def test_login_from_foreign_origin_is_refused(
    client: httpx.AsyncClient, session_factory: SessionFactory, origin: str
) -> None:
    await register(client, "alice")

    response = await client.post(LOGIN_URL, json=CREDENTIALS, headers={"Origin": origin})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert "set-cookie" not in response.headers
    assert await count(session_factory, AuthSession) == 0


async def test_register_from_foreign_origin_is_refused(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    response = await client.post(
        REGISTER_URL,
        json={**CREDENTIALS, "role": "passenger"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert await count(session_factory, User) == 0


@pytest.mark.parametrize(
    "origin",
    [FRONTEND, "HTTP://LOCALHOST:5173", "https://testserver", "https://testserver:443"],
    ids=["allowlisted", "allowlisted-other-case", "same-origin", "same-origin-default-port"],
)
async def test_allowed_or_same_origin_can_register_and_log_in(
    client: httpx.AsyncClient, origin: str
) -> None:
    headers = {"Origin": origin}

    registered = await client.post(
        REGISTER_URL, json={**CREDENTIALS, "role": "passenger"}, headers=headers
    )
    logged_in = await client.post(LOGIN_URL, json=CREDENTIALS, headers=headers)

    assert (registered.status_code, logged_in.status_code) == (201, 200)


async def test_request_without_origin_is_allowed(client: httpx.AsyncClient) -> None:
    await register(client, "alice")

    assert (await client.post(LOGIN_URL, json=CREDENTIALS)).status_code == 200
