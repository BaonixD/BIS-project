"""The application owns one routing provider: OSRM, openrouteservice or one injected by tests."""

import httpx
import pytest
from fastapi import FastAPI

from support.auth import register_and_login
from support.clock import ManualClock
from support.routing import FakeRoutingProvider, isolate_routing_environment
from taxi_service.core.config import Settings
from taxi_service.main import create_app
from taxi_service.modules.geo.client import OpenRouteServiceClient
from taxi_service.modules.geo.osrm import OsrmClient


@pytest.fixture(autouse=True)
def _no_routing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_routing_environment(monkeypatch)


@pytest.fixture
def app(settings: Settings, clock: ManualClock) -> FastAPI:
    """The real routing wiring, unlike the shared fixture's fake provider."""
    return create_app(settings, clock=clock)


async def test_app_starts_without_routing_settings_and_uses_osrm(settings: Settings) -> None:
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.routing_provider, OsrmClient)


async def test_app_uses_openrouteservice_when_selected(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROUTING_PROVIDER", "openrouteservice")
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.routing_provider, OpenRouteServiceClient)


async def test_route_without_osrm_url_is_unavailable(client: httpx.AsyncClient) -> None:
    user = await register_and_login(client, "pat")

    response = await client.post(
        "/api/v1/geo/route",
        json={
            "origin": {"longitude": 76.9572, "latitude": 43.2389},
            "destination": {"longitude": 76.9286, "latitude": 43.2187},
        },
        headers=user.csrf_headers,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "routing_unavailable"


async def test_lifespan_closes_its_routing_http_client(settings: Settings) -> None:
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        http = app.state.routing_http_client
        assert not http.is_closed

    assert http.is_closed


async def test_restarted_app_gets_a_new_routing_http_client(settings: Settings) -> None:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        first = app.state.routing_http_client

    async with app.router.lifespan_context(app):
        second = app.state.routing_http_client
        assert second is not first
        assert not second.is_closed


async def test_injected_provider_is_used_without_an_http_client(settings: Settings) -> None:
    provider = FakeRoutingProvider()
    app = create_app(settings, routing_provider=provider)

    for _ in range(2):
        async with app.router.lifespan_context(app):
            assert app.state.routing_provider is provider
            assert app.state.routing_http_client is None
