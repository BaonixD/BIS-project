"""OpenAPI documents the session/CSRF schemes and the unified error envelope."""

from typing import Any

import httpx
import pytest

ERROR_REF = "#/components/schemas/ErrorResponse"


@pytest.fixture
async def schema(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    document: dict[str, Any] = response.json()
    return document


def operation(schema: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    result: dict[str, Any] = schema["paths"][f"/api/v1{path}"][method]
    return result


def error_statuses(op: dict[str, Any]) -> set[str]:
    return {
        status
        for status, response in op["responses"].items()
        if response.get("content", {}).get("application/json", {}).get("schema")
        == {"$ref": ERROR_REF}
    }


def test_session_cookie_and_csrf_header_are_security_schemes(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]

    assert schemes["SessionCookie"] | {"description": ""} == {
        "type": "apiKey",
        "in": "cookie",
        "name": "taxi_session",
        "description": "",
    }
    assert schemes["CsrfToken"]["in"] == "header"
    assert schemes["CsrfToken"]["name"] == "X-CSRF-Token"
    assert "auth/login" in schemes["SessionCookie"]["description"]
    assert "auth/session" in schemes["CsrfToken"]["description"]


def test_protected_operations_declare_the_session_scheme(schema: dict[str, Any]) -> None:
    for method, path in [("get", "/auth/session"), ("post", "/auth/logout")]:
        security = operation(schema, method, path)["security"]
        assert any("SessionCookie" in requirement for requirement in security)


def test_public_operations_need_no_session(schema: dict[str, Any]) -> None:
    for path in ("/auth/register", "/auth/login"):
        assert "security" not in operation(schema, "post", path)


def test_validation_errors_use_the_unified_envelope(schema: dict[str, Any]) -> None:
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "422" in error_statuses(operation(schema, "post", "/auth/register"))


@pytest.mark.parametrize(
    ("method", "path", "statuses"),
    [
        ("post", "/auth/register", {"403", "409", "422"}),
        ("post", "/auth/login", {"401", "403", "422", "429"}),
        ("post", "/auth/logout", {"401", "403"}),
        ("get", "/auth/session", {"401"}),
    ],
)
def test_auth_errors_are_documented(
    schema: dict[str, Any], method: str, path: str, statuses: set[str]
) -> None:
    assert statuses <= error_statuses(operation(schema, method, path))


def test_every_error_response_of_api_v1_uses_the_envelope(schema: dict[str, Any]) -> None:
    for path, operations in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for op in operations.values():
            errors = {status for status in op["responses"] if not status.startswith("2")}
            assert errors <= error_statuses(op), path
