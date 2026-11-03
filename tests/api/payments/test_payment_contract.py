"""Payment routes in OpenAPI: documented errors, session scheme, closed request bodies."""

from typing import Any

import httpx
import pytest

ERROR_REF = "#/components/schemas/ErrorResponse"
BASE = "/api/v1/rides/{ride_id}/payment"


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
    ("method", "path", "errors"),
    [
        ("get", BASE, {"401", "404", "409", "422"}),
        ("put", f"{BASE}/method", {"401", "403", "404", "409", "422", "503"}),
        ("post", f"{BASE}/report", {"401", "403", "404", "409", "422"}),
        ("post", f"{BASE}/confirm", {"401", "403", "404", "409", "422"}),
    ],
)
def test_payment_operations_document_their_responses(
    schema: dict[str, Any], method: str, path: str, errors: set[str]
) -> None:
    operation = schema["paths"][path][method]

    assert "200" in operation["responses"]
    assert errors <= error_statuses(operation)
    assert any("SessionCookie" in requirement for requirement in operation["security"])


@pytest.mark.parametrize(
    "name", ["PaymentMethodRequest", "PaymentReportRequest", "PaymentConfirmRequest"]
)
def test_request_bodies_forbid_extra_fields(schema: dict[str, Any], name: str) -> None:
    body = schema["components"]["schemas"][name]

    assert body["additionalProperties"] is False
    assert not {"amount_kzt", "payment_url", "status", "verification"} & set(body["properties"])


def test_responses_state_manual_verification(schema: dict[str, Any]) -> None:
    verification = schema["components"]["schemas"]["PaymentResponse"]["properties"]["verification"]

    assert verification.get("const") == "manual" or verification.get("enum") == ["manual"]
