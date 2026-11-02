"""Ride routes in OpenAPI, and the idempotency headers through CORS for a browser client."""

from typing import Any

import httpx
import pytest

from support.rides import QUOTES_URL, RIDES_URL
from taxi_service.core.config import Settings

ERROR_REF = "#/components/schemas/ErrorResponse"
FRONTEND = "http://localhost:5173"


@pytest.fixture
async def schema(client: httpx.AsyncClient) -> dict[str, Any]:
    document: dict[str, Any] = (await client.get("/openapi.json")).json()
    return document


def error_statuses(operation: dict[str, Any]) -> set[str]:
    return {
        status
        for status, response in operation["responses"].items()
        if response.get("content", {}).get("application/json", {}).get("schema")
        == {"$ref": ERROR_REF}
    }


@pytest.mark.parametrize(
    ("method", "path", "success", "errors"),
    [
        ("post", "/rides/quotes", "201", {"401", "403", "422", "503"}),
        ("post", "/rides", "201", {"401", "403", "404", "409", "422"}),
        ("get", "/rides/{ride_id}", "200", {"401", "404", "422"}),
    ],
)
def test_ride_operations_document_their_responses(
    schema: dict[str, Any], method: str, path: str, success: str, errors: set[str]
) -> None:
    operation = schema["paths"][f"/api/v1{path}"][method]

    assert success in operation["responses"]
    assert errors <= error_statuses(operation)
    assert {"SessionCookie": []} in operation["security"]


def test_ride_creation_documents_the_idempotency_key(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/api/v1/rides"]["post"]["parameters"]

    [header] = [item for item in parameters if item["in"] == "header"]
    assert header["name"] == "Idempotency-Key"
    assert "Required" in header["description"]


class TestBrowserClient:
    @pytest.fixture
    def settings(self, settings: Settings) -> Settings:
        return settings.model_copy(update={"cors_allowed_origins": [FRONTEND]})

    async def test_preflight_allows_the_idempotency_key(self, client: httpx.AsyncClient) -> None:
        response = await client.options(
            RIDES_URL,
            headers={
                "Origin": FRONTEND,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token,idempotency-key",
            },
        )

        assert response.status_code == 200
        assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()

    async def test_replay_header_is_exposed(self, client: httpx.AsyncClient) -> None:
        response = await client.post(QUOTES_URL, headers={"Origin": FRONTEND})

        exposed = response.headers["access-control-expose-headers"].lower()
        assert "idempotent-replayed" in exposed
