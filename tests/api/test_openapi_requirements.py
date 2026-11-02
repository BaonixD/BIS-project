"""OpenAPI states what the server really requires: cookie AND CSRF, and Idempotency-Key."""

from typing import Any

import httpx
import pytest

SAFE_METHODS = {"get", "head", "options"}
SESSION_ONLY = [{"SessionCookie": []}]
SESSION_AND_CSRF = [{"SessionCookie": [], "CsrfToken": []}]


@pytest.fixture
async def schema(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/openapi.json")
    document: dict[str, Any] = response.json()
    return document


def protected_operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, operation)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if operation.get("security")
    ]


def test_state_changes_need_both_the_session_and_the_csrf_token(schema: dict[str, Any]) -> None:
    unsafe = [op for op in protected_operations(schema) if op[0] not in SAFE_METHODS]

    assert unsafe
    for method, path, operation in unsafe:
        assert operation["security"] == SESSION_AND_CSRF, (method, path)


def test_reads_need_only_the_session(schema: dict[str, Any]) -> None:
    safe = [op for op in protected_operations(schema) if op[0] in SAFE_METHODS]

    assert safe
    for method, path, operation in safe:
        assert operation["security"] == SESSION_ONLY, (method, path)


def test_ride_creation_documents_the_required_idempotency_key(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/api/v1/rides"]["post"]["parameters"]

    [header] = [p for p in parameters if p["in"] == "header" and p["name"] == "Idempotency-Key"]
    assert header["required"] is True
