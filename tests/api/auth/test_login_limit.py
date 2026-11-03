"""Login attempts per username are limited (defaults: 5 per 15 minutes, app clock)."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from support.auth import login, register
from support.clock import ManualClock
from taxi_service.core.config import Settings

WINDOW = timedelta(seconds=900)
WRONG = "wrong-password-123"


async def fail_logins(client: httpx.AsyncClient, username: str, times: int) -> None:
    for _ in range(times):
        assert (await login(client, username, password=WRONG)).status_code == 401


async def test_sixth_attempt_is_refused_even_with_the_right_password(
    client: httpx.AsyncClient,
) -> None:
    await register(client, "alice")
    await fail_logins(client, "alice", 3)
    await fail_logins(client, "ALICE", 2)  # the limit ignores username case

    response = await login(client, "alice")

    assert response.status_code == 429
    assert response.json()["error"] == {
        "code": "too_many_attempts",
        "message": "Too many login attempts; try again later.",
        "details": {"retry_after_seconds": 900},
    }
    assert "set-cookie" not in response.headers


async def test_unknown_usernames_are_limited_the_same_way(client: httpx.AsyncClient) -> None:
    await fail_logins(client, "ghost", 5)

    assert (await login(client, "ghost")).status_code == 429


async def test_attempts_are_allowed_again_after_the_window(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    await register(client, "alice")
    await fail_logins(client, "alice", 5)

    clock.advance(WINDOW)

    assert (await login(client, "alice")).status_code == 200


async def test_successful_login_resets_the_count(client: httpx.AsyncClient) -> None:
    await register(client, "alice")
    await fail_logins(client, "alice", 4)
    assert (await login(client, "alice")).status_code == 200

    await fail_logins(client, "alice", 5)

    assert (await login(client, "alice")).status_code == 429


async def test_other_usernames_are_not_affected(client: httpx.AsyncClient) -> None:
    await register(client, "bob")
    await fail_logins(client, "alice", 5)

    assert (await login(client, "bob")).status_code == 200


class TestBoundedStorage:
    @pytest.fixture
    def settings(self, settings: Settings) -> Settings:
        return settings.model_copy(update={"login_limiter_max_keys": 2})

    async def test_limiter_keeps_at_most_the_configured_number_of_keys(
        self, app: FastAPI, client: httpx.AsyncClient
    ) -> None:
        for username in ("user_a", "user_b", "user_c", "user_d"):
            await login(client, username, password=WRONG)

        assert len(app.state.login_limiter) == 2
