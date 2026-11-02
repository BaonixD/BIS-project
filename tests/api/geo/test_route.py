"""POST /api/v1/geo/route: road route for any logged-in user, errors in the envelope."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.auth import CSRF_HEADER, register_and_login
from support.clock import ManualClock
from support.routing import FakeRoutingProvider, fake_route
from taxi_service.core.config import Settings
from taxi_service.core.errors import AppError
from taxi_service.main import create_app
from taxi_service.modules.geo.client import (
    OpenRouteServiceClient,
    RoutingProvider,
    create_routing_http_client,
)
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteResult

ROUTE_URL = "/api/v1/geo/route"
ABAY_DOSTYK = {"longitude": 76.9572, "latitude": 43.2389}
AL_FARABI = {"longitude": 76.9286, "latitude": 43.2187}
ROUTE_BODY = {"origin": ABAY_DOSTYK, "destination": AL_FARABI}
SECRET_KEY = "eyJ-secret-routing-key-91c4"


@pytest.fixture
def routing_provider() -> FakeRoutingProvider:
    return FakeRoutingProvider()


@pytest.fixture
def app(settings: Settings, clock: ManualClock, routing_provider: RoutingProvider) -> FastAPI:
    return create_app(settings, clock=clock, routing_provider=routing_provider)


def error_of(response: httpx.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert set(body) == {"error", "request_id"}
    assert body["request_id"] == response.headers["X-Request-ID"]
    error: dict[str, Any] = body["error"]
    return error


async def logged_in_headers(client: httpx.AsyncClient, role: str = "passenger") -> dict[str, str]:
    user = await register_and_login(client, f"{role}_1", role=role)
    return user.csrf_headers


# Authentication and CSRF


async def test_route_needs_a_session(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    response = await client.post(ROUTE_URL, json=ROUTE_BODY)

    assert response.status_code == 401
    assert error_of(response)["code"] == "not_authenticated"
    assert routing_provider.call_count == 0


@pytest.mark.parametrize("headers", [{}, {CSRF_HEADER: "not-the-session-token"}])
async def test_route_needs_the_sessions_csrf_token(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider, headers: dict[str, str]
) -> None:
    await register_and_login(client, "pat")

    response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.status_code == 403
    assert error_of(response)["code"] == "csrf_failed"
    assert routing_provider.call_count == 0


# Successful route


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_any_role_gets_the_providers_route(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider, role: str
) -> None:
    headers = await logged_in_headers(client, role)

    response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.status_code == 200
    origin, destination = Coordinates(**ABAY_DOSTYK), Coordinates(**AL_FARABI)
    assert routing_provider.calls == [(origin, destination)]
    assert response.json() == fake_route(origin, destination).model_dump(mode="json")


async def test_route_has_the_spec_shape_in_lon_lat_order(client: httpx.AsyncClient) -> None:
    headers = await logged_in_headers(client)

    body = (await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)).json()

    assert set(body) == {"distance_m", "duration_s", "route_geometry", "provider"}
    assert (body["distance_m"], body["duration_s"], body["provider"]) == (10_000, 1_500, "fake")
    geometry = body["route_geometry"]
    assert geometry["type"] == "LineString"
    assert geometry["coordinates"][0] == [76.9572, 43.2389]
    assert geometry["coordinates"][-1] == [76.9286, 43.2187]
    assert "price" not in body
    assert "amount_kzt" not in body


async def test_route_is_returned_unchanged(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    route = RouteResult.model_validate(
        {
            "distance_m": 4121,
            "duration_s": 610,
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[76.9572, 43.2389], [76.941, 43.2295], [76.9286, 43.2187]],
            },
            "provider": "openrouteservice",
        }
    )
    routing_provider.route = route
    headers = await logged_in_headers(client)

    response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.json() == route.model_dump(mode="json")


# Request validation


@pytest.mark.parametrize(
    "body",
    [
        {"origin": ABAY_DOSTYK},
        {"origin": {"longitude": 76.9572, "latitude": 90.5}, "destination": AL_FARABI},
        {"origin": {"longitude": -180.1, "latitude": 43.2}, "destination": AL_FARABI},
        {"origin": {"longitude": "76.9572", "latitude": 43.2389}, "destination": AL_FARABI},
        {"origin": {"lon": 76.9572, "lat": 43.2389}, "destination": AL_FARABI},
        {"origin": [76.9572, 43.2389], "destination": AL_FARABI},
        {**ROUTE_BODY, "price": 100},
        {"origin": {**ABAY_DOSTYK, "altitude": 800}, "destination": AL_FARABI},
        [ABAY_DOSTYK, AL_FARABI],
    ],
)
async def test_invalid_request_is_a_validation_error(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider, body: Any
) -> None:
    headers = await logged_in_headers(client)

    response = await client.post(ROUTE_URL, json=body, headers=headers)

    assert response.status_code == 422
    assert error_of(response)["code"] == "validation_error"
    assert routing_provider.call_count == 0


async def test_identical_points_are_refused_before_the_provider(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    headers = await logged_in_headers(client)

    response = await client.post(
        ROUTE_URL, json={"origin": ABAY_DOSTYK, "destination": dict(ABAY_DOSTYK)}, headers=headers
    )

    assert response.status_code == 422
    assert error_of(response)["code"] == "route_points_identical"
    assert routing_provider.call_count == 0


async def test_nearby_distinct_points_reach_the_provider(
    client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    headers = await logged_in_headers(client)
    nearby = {"longitude": 76.9572, "latitude": 43.23891}

    response = await client.post(
        ROUTE_URL, json={"origin": ABAY_DOSTYK, "destination": nearby}, headers=headers
    )

    assert response.status_code == 200
    assert routing_provider.call_count == 1


# OpenAPI


async def test_openapi_documents_the_route_and_its_errors(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"][ROUTE_URL]["post"]

    assert {"SessionCookie": []} in operation["security"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RouteRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RouteResult"
    }
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    for status in ("401", "403", "422", "503"):
        response = operation["responses"][status]
        assert response["content"]["application/json"]["schema"] == error_ref, status
    description = operation["description"]
    for code in ("route_points_identical", "route_not_found", "routing_unavailable"):
        assert code in description
    assert "routing_provider_error" in description


# Provider errors


@pytest.mark.parametrize(
    ("error", "status", "code", "details"),
    [
        (RoutingUnavailableError(), 503, "routing_unavailable", {}),
        (
            RoutingProviderError("timeout"),
            503,
            "routing_provider_error",
            {"reason": "timeout", "provider_status": None},
        ),
        (
            RoutingProviderError("rate_limited", provider_status=429),
            503,
            "routing_provider_error",
            {"reason": "rate_limited", "provider_status": 429},
        ),
        (
            RoutingProviderError("invalid_response", provider_status=200),
            503,
            "routing_provider_error",
            {"reason": "invalid_response", "provider_status": 200},
        ),
        (RouteNotFoundError(), 422, "route_not_found", {}),
    ],
)
async def test_provider_errors_keep_status_and_code(
    client: httpx.AsyncClient,
    routing_provider: FakeRoutingProvider,
    error: AppError,
    status: int,
    code: str,
    details: dict[str, Any],
) -> None:
    routing_provider.fail_with(error)
    headers = await logged_in_headers(client)

    response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.status_code == status
    assert error_of(response) | {"message": ""} == {
        "code": code,
        "message": "",
        "details": details,
    }


async def test_route_request_holds_no_database_connection(
    app: FastAPI, client: httpx.AsyncClient, routing_provider: FakeRoutingProvider
) -> None:
    checked_out: list[int] = []

    class PoolProbe:
        async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
            checked_out.append(app.state.engine.pool.checkedout())
            return await routing_provider.get_route(origin, destination)

    app.state.routing_provider = PoolProbe()
    headers = await logged_in_headers(client)

    response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.status_code == 200
    assert checked_out == [0]


# The real adapter behind the endpoint, on a mock transport


@asynccontextmanager
async def openrouteservice(
    app: FastAPI, reply: httpx.Response, *, api_key: str | None
) -> AsyncIterator[list[httpx.Request]]:
    """Put the real adapter in ``app``; yields the requests it sends."""
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return reply

    settings = RoutingSettings(_env_file=None, api_key=api_key, max_retries=0)
    transport = httpx.MockTransport(handle)
    async with create_routing_http_client(settings, transport=transport) as http:
        app.state.routing_provider = OpenRouteServiceClient.from_settings(settings, http)
        yield requests


async def test_real_adapter_without_key_sends_no_request(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    headers = await logged_in_headers(client)

    async with openrouteservice(app, httpx.Response(200), api_key=None) as requests:
        response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert response.status_code == 503
    assert error_of(response)["code"] == "routing_unavailable"
    assert requests == []


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (
            httpx.Response(403, json={"error": f"Access to this API denied {SECRET_KEY}"}),
            "rejected",
        ),
        (httpx.Response(500, text=f"upstream failure for {SECRET_KEY}"), "provider_unavailable"),
    ],
)
async def test_real_adapter_failure_never_reveals_the_key(
    app: FastAPI, client: httpx.AsyncClient, reply: httpx.Response, reason: str
) -> None:
    headers = await logged_in_headers(client)

    async with openrouteservice(app, reply, api_key=SECRET_KEY) as requests:
        response = await client.post(ROUTE_URL, json=ROUTE_BODY, headers=headers)

    assert len(requests) == 1
    assert response.status_code == 503
    assert error_of(response)["details"]["reason"] == reason
    assert SECRET_KEY not in response.text
    assert all(SECRET_KEY not in value for value in response.headers.values())
