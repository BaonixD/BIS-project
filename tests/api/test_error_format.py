import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

SECRET_PASSWORD = "short-pw"
INTERNAL_FAILURE = "sensitive internal failure"


class Credentials(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=10)


def _probe_router() -> APIRouter:
    router = APIRouter(prefix="/_probe")

    @router.get("/items/{item_id}")
    async def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @router.post("/credentials")
    async def check_credentials(credentials: Credentials) -> dict[str, str]:
        return {"username": credentials.username}

    @router.get("/nonstandard")
    async def nonstandard() -> None:
        raise HTTPException(status_code=499)

    @router.get("/failure")
    async def fail() -> None:
        raise RuntimeError(INTERNAL_FAILURE)

    return router


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    app.include_router(_probe_router())
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # Unhandled errors must surface as HTTP 500 responses, not test exceptions.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def assert_error_envelope(response: httpx.Response, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code
    assert response.headers["content-type"] == "application/json"
    body: dict[str, Any] = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]
    assert isinstance(body["error"]["details"], dict)
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


async def test_unknown_route_returns_not_found_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/no-such-route")

    body = assert_error_envelope(response, 404, "not_found")
    assert body["error"]["details"] == {}


async def test_wrong_method_returns_method_not_allowed_envelope(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/health/live")

    assert_error_envelope(response, 405, "method_not_allowed")
    assert response.headers["Allow"] == "GET"


async def test_invalid_path_parameter_returns_validation_envelope(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/_probe/items/not-a-number")

    body = assert_error_envelope(response, 422, "validation_error")
    [error] = body["error"]["details"]["errors"]
    assert error["loc"] == ["path", "item_id"]
    assert error["type"] == "int_parsing"
    assert error["msg"]


async def test_validation_details_do_not_echo_submitted_values(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/_probe/credentials", json={"username": "rider_1", "password": SECRET_PASSWORD}
    )

    body = assert_error_envelope(response, 422, "validation_error")
    [error] = body["error"]["details"]["errors"]
    assert error["loc"] == ["body", "password"]
    assert set(error) == {"loc", "msg", "type"}
    assert SECRET_PASSWORD not in response.text


async def test_malformed_json_returns_validation_envelope(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/_probe/credentials",
        content=b'{"username": ',
        headers={"Content-Type": "application/json"},
    )

    assert_error_envelope(response, 422, "validation_error")


async def test_unhandled_exception_returns_generic_internal_error(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/_probe/failure", headers={"X-Request-ID": "trace-500"})

    body = assert_error_envelope(response, 500, "internal_error")
    assert body["request_id"] == "trace-500"
    assert body["error"]["details"] == {}
    assert INTERNAL_FAILURE not in response.text


async def test_unhandled_exception_is_logged_with_request_id(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="taxi_service"):
        await client.get("/_probe/failure", headers={"X-Request-ID": "trace-log"})

    [record] = [r for r in caplog.records if r.name.startswith("taxi_service")]
    assert record.exc_info is not None
    assert getattr(record, "request_id", None) == "trace-log"


async def test_nonstandard_http_status_keeps_status_in_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/_probe/nonstandard")

    assert_error_envelope(response, 499, "http_error")
