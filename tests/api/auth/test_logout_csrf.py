"""Logout revokes the session; state-changing requests need the session's CSRF token."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from sqlalchemy import select

from support.auth import (
    CSRF_HEADER,
    LOGOUT_URL,
    SESSION_COOKIE,
    SESSION_URL,
    current_session,
    login,
    register_and_login,
)
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.auth.models import AuthSession

PROTECTED_URL = "/_probe/protected"


def _probe_router() -> APIRouter:
    router = APIRouter()

    @router.get(PROTECTED_URL)
    async def read_protected(user: CurrentUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    @router.post(PROTECTED_URL)
    async def change_protected(user: CurrentUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    @router.delete(PROTECTED_URL)
    async def delete_protected(user: CurrentUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    return router


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    app.include_router(_probe_router())
    return app


@pytest.fixture
async def other_client(app: FastAPI, client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    """A second browser on the same running application (``client`` runs the lifespan)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=client.base_url) as other:
        yield other


def assert_error(response: httpx.Response, status_code: int, code: str) -> None:
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code


async def test_register_login_session_protected_logout_then_unauthenticated(
    client: httpx.AsyncClient,
) -> None:
    user = await register_and_login(client, "alice")

    protected = await client.post(PROTECTED_URL, headers=user.csrf_headers)
    assert protected.status_code == 200
    assert protected.json() == {"user_id": str(user.id)}

    logout = await client.post(LOGOUT_URL, headers=user.csrf_headers)
    assert logout.status_code == 204
    assert f'{SESSION_COOKIE}=""' in logout.headers["set-cookie"]
    assert "max-age=0" in logout.headers["set-cookie"].lower()

    assert_error(await client.get(SESSION_URL), 401, "not_authenticated")
    assert_error(
        await client.post(PROTECTED_URL, headers=user.csrf_headers), 401, "not_authenticated"
    )


async def test_logout_revokes_the_session_in_the_database(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    user = await register_and_login(client, "alice")
    token = client.cookies[SESSION_COOKIE]

    await client.post(LOGOUT_URL, headers=user.csrf_headers)

    async with session_factory() as session, read_transaction(session):
        [stored] = list(await session.scalars(select(AuthSession)))
    assert stored.revoked_at is not None
    # Replaying the old cookie after logout does not bring the session back.
    client.cookies.set(SESSION_COOKIE, token, domain="testserver")
    assert_error(await client.get(SESSION_URL), 401, "not_authenticated")


async def test_logout_without_session_is_not_authenticated(client: httpx.AsyncClient) -> None:
    assert_error(await client.post(LOGOUT_URL), 401, "not_authenticated")


async def test_safe_methods_do_not_need_csrf_token(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")

    assert (await client.get(PROTECTED_URL)).status_code == 200


@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_state_change_without_csrf_token_is_refused(
    client: httpx.AsyncClient, method: str
) -> None:
    await register_and_login(client, "alice")

    assert_error(await client.request(method, PROTECTED_URL), 403, "csrf_failed")


async def test_logout_without_csrf_token_keeps_the_session(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")

    assert_error(await client.post(LOGOUT_URL), 403, "csrf_failed")

    assert (await client.get(SESSION_URL)).status_code == 200


async def test_wrong_csrf_token_is_refused(client: httpx.AsyncClient) -> None:
    user = await register_and_login(client, "alice")

    response = await client.post(PROTECTED_URL, headers={CSRF_HEADER: user.csrf_token + "x"})

    assert_error(response, 403, "csrf_failed")


async def test_csrf_token_of_another_session_is_refused(
    client: httpx.AsyncClient, other_client: httpx.AsyncClient
) -> None:
    await register_and_login(client, "alice")
    bob = await register_and_login(other_client, "bob")

    assert_error(await client.post(PROTECTED_URL, headers=bob.csrf_headers), 403, "csrf_failed")


async def test_csrf_token_of_a_logged_out_session_stops_working(
    client: httpx.AsyncClient,
) -> None:
    old = await register_and_login(client, "alice")
    await client.post(LOGOUT_URL, headers=old.csrf_headers)
    assert (await login(client, "alice")).status_code == 200

    new = await current_session(client)

    assert new.csrf_token != old.csrf_token
    assert_error(await client.post(PROTECTED_URL, headers=old.csrf_headers), 403, "csrf_failed")
    assert (await client.post(PROTECTED_URL, headers=new.csrf_headers)).status_code == 200
