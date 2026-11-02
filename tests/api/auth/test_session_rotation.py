"""Logging in again replaces the browser's session: the previous one is revoked."""

import httpx

from support.auth import (
    SESSION_COOKIE,
    SESSION_URL,
    login,
    register,
    register_and_login,
    use_session_token,
)


async def test_new_login_revokes_the_session_it_replaces(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")
    previous = client.cookies[SESSION_COOKIE]

    await login(client, "alice")
    current = client.cookies[SESSION_COOKIE]

    assert current != previous
    assert (await client.get(SESSION_URL)).status_code == 200
    use_session_token(client, previous)
    assert (await client.get(SESSION_URL)).status_code == 401


async def test_switching_user_revokes_the_previous_users_session(
    client: httpx.AsyncClient,
) -> None:
    await register_and_login(client, "alice")
    alice_token = client.cookies[SESSION_COOKIE]
    await register(client, "bob")

    await login(client, "bob")

    assert (await client.get(SESSION_URL)).json()["user"]["username"] == "bob"
    use_session_token(client, alice_token)
    assert (await client.get(SESSION_URL)).status_code == 401


async def test_failed_login_keeps_the_existing_session(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")

    assert (await login(client, "alice", password="wrong-password-123")).status_code == 401

    assert (await client.get(SESSION_URL)).status_code == 200


async def test_sessions_of_other_browsers_stay_valid(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")
    first_browser = client.cookies[SESSION_COOKIE]
    client.cookies.clear()

    await login(client, "alice")

    use_session_token(client, first_browser)
    assert (await client.get(SESSION_URL)).status_code == 200
