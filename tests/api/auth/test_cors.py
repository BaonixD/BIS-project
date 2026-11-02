"""Credentialed CORS only for CORS_ALLOWED_ORIGINS; never a wildcard."""

import httpx
import pytest

from support.auth import LOGIN_URL, SESSION_URL
from taxi_service.core.config import Settings

FRONTEND = "http://localhost:5173"


def preflight_headers(origin: str) -> dict[str, str]:
    return {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-token",
    }


class TestWithAllowlist:
    @pytest.fixture
    def settings(self, settings: Settings) -> Settings:
        return settings.model_copy(update={"cors_allowed_origins": [FRONTEND]})

    async def test_preflight_from_allowed_origin_permits_credentials_and_csrf_header(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.options(LOGIN_URL, headers=preflight_headers(FRONTEND))

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == FRONTEND
        assert response.headers["access-control-allow-credentials"] == "true"
        allowed_headers = response.headers["access-control-allow-headers"].lower()
        assert "x-csrf-token" in allowed_headers
        assert "content-type" in allowed_headers

    async def test_preflight_from_other_origin_is_not_allowed(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.options(
            LOGIN_URL, headers=preflight_headers("https://evil.example")
        )

        assert "access-control-allow-origin" not in response.headers

    async def test_actual_response_exposes_request_id_to_allowed_origin(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get(SESSION_URL, headers={"Origin": FRONTEND})

        assert response.status_code == 401  # errors are readable by the frontend too
        assert response.headers["access-control-allow-origin"] == FRONTEND
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "x-request-id" in response.headers["access-control-expose-headers"].lower()

    async def test_other_origin_gets_no_cors_headers(self, client: httpx.AsyncClient) -> None:
        response = await client.get(SESSION_URL, headers={"Origin": "https://evil.example"})

        assert "access-control-allow-origin" not in response.headers


async def test_default_empty_allowlist_allows_no_cross_origin_access(
    client: httpx.AsyncClient,
) -> None:
    response = await client.options(LOGIN_URL, headers=preflight_headers(FRONTEND))

    assert response.headers.get("access-control-allow-origin") not in (FRONTEND, "*")
