"""Payment routes in OpenAPI: documented errors, session scheme, the method in the order."""

from typing import Any

import httpx
import pytest

ERROR_REF = "#/components/schemas/ErrorResponse"
BASE = "/api/v1/rides/{ride_id}/payment"
CASH_RECEIVED = f"{BASE}/cash-received"


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
        ("get", BASE, {"401", "404", "422"}),
        ("post", CASH_RECEIVED, {"401", "403", "404", "409", "422"}),
        ("post", "/api/v1/rides", {"401", "403", "404", "409", "422", "503"}),
    ],
)
def test_payment_operations_document_their_responses(
    schema: dict[str, Any], method: str, path: str, errors: set[str]
) -> None:
    operation = schema["paths"][path][method]

    assert {"200", "201"} & set(operation["responses"])
    assert errors <= error_statuses(operation)
    assert any("SessionCookie" in requirement for requirement in operation["security"])


def test_only_reading_and_cash_received_remain(schema: dict[str, Any]) -> None:
    assert {path for path in schema["paths"] if path.startswith(BASE)} == {BASE, CASH_RECEIVED}
    assert set(schema["paths"][CASH_RECEIVED]) == {"post"}
    assert "requestBody" not in schema["paths"][CASH_RECEIVED]["post"]
    assert "PaymentMethodRequest" not in schema["components"]["schemas"]


def test_order_takes_the_payment_method(schema: dict[str, Any]) -> None:
    body = schema["components"]["schemas"]["RideCreateRequest"]

    assert body["additionalProperties"] is False
    assert set(body["properties"]) == {"quote_id", "payment_method"}
    assert body["required"] == ["quote_id"]
    assert body["properties"]["payment_method"]["default"] == "cash"


def test_response_has_the_payment_fields(schema: dict[str, Any]) -> None:
    components = schema["components"]["schemas"]

    assert set(components["PaymentResponse"]["properties"]) == {
        "ride_id",
        "amount_kzt",
        "currency",
        "method",
        "status",
        "paid_at",
        "refunded_at",
        "payment_url",
    }
    assert sorted(components["PaymentStatus"]["enum"]) == ["paid", "refunded", "unpaid"]
    assert sorted(components["PaymentMethod"]["enum"]) == ["cash", "kaspi_link"]
    for name in ("RideResponse", "RideDetailsResponse", "RideSummary"):
        assert {"payment_method", "payment_status"} <= set(components[name]["properties"])
