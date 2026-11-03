"""SESSION_COOKIE_SECURE=false (local HTTP development): the cookie has no Secure flag."""

import httpx
import pytest

from support.auth import login, register
from taxi_service.core.config import Settings


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"session_cookie_secure": False})


async def test_cookie_without_secure_flag_when_disabled(client: httpx.AsyncClient) -> None:
    await register(client, "alice")

    response = await login(client, "alice")

    attributes = {part.strip().lower() for part in response.headers["set-cookie"].split(";")}
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert "secure" not in attributes
