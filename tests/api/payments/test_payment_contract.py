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
        ("post", f"{BASE}/pay", {"401", "403", "404", "409", "422"}),
    ],
)
def test_payment_operations_document_their_responses(
    schema: dict[str, Any], method: str, path: str, errors: set[str]
) -> None:
    operation = schema["paths"][path][method]

    assert "200" in operation["responses"]
    assert errors <= error_statuses(operation)
    assert any("SessionCookie" in requirement for requirement in operation["security"])


def test_report_and_confirm_are_gone(schema: dict[str, Any]) -> None:
    assert {path for path in schema["paths"] if path.startswith(BASE)} == {
        BASE,
        f"{BASE}/method",
        f"{BASE}/pay",
    }
    assert "requestBody" not in schema["paths"][f"{BASE}/pay"]["post"]


def test_method_request_forbids_extra_fields(schema: dict[str, Any]) -> None:
    body = schema["components"]["schemas"]["PaymentMethodRequest"]

    assert body["additionalProperties"] is False
    assert set(body["properties"]) == {"method"}


def test_response_has_the_simple_payment_fields(schema: dict[str, Any]) -> None:
    response = schema["components"]["schemas"]["PaymentResponse"]

    assert set(response["properties"]) == {
        "ride_id",
        "amount_kzt",
        "currency",
        "method",
        "status",
        "paid_at",
        "payment_url",
    }
    status = schema["components"]["schemas"]["PaymentStatus"]
    assert sorted(status["enum"]) == ["paid", "unpaid"]
