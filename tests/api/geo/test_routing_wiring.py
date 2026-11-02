"""The application owns one routing provider: openrouteservice, or one injected by tests."""

from support.routing import FakeRoutingProvider
from taxi_service.core.config import Settings
from taxi_service.main import create_app
from taxi_service.modules.geo.client import OpenRouteServiceClient


async def test_app_starts_without_routing_key_and_uses_openrouteservice(
    settings: Settings,
) -> None:
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.routing_provider, OpenRouteServiceClient)


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
