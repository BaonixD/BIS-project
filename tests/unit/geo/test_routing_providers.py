import httpx
import pytest

from support.routing import isolate_routing_environment
from taxi_service.modules.geo.client import (
    OpenRouteServiceClient,
    RoutingProvider,
    create_routing_http_client,
)
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import RouteNotFoundError
from taxi_service.modules.geo.osrm import OsrmClient
from taxi_service.modules.geo.providers import create_routing_provider
from taxi_service.modules.geo.schemas import Coordinates

ORIGIN = Coordinates(longitude=76.9572, latitude=43.2389)
DESTINATION = Coordinates(longitude=76.9286, latitude=43.2187)


@pytest.fixture(autouse=True)
def _isolate_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_routing_environment(monkeypatch)


async def provider_for(settings: RoutingSettings) -> RoutingProvider:
    async with create_routing_http_client(settings) as http:
        return create_routing_provider(settings, http)


async def test_osrm_is_built_by_default() -> None:
    provider = await provider_for(RoutingSettings(_env_file=None))

    assert isinstance(provider, OsrmClient)


async def test_openrouteservice_is_built_when_selected() -> None:
    provider = await provider_for(RoutingSettings(_env_file=None, provider="openrouteservice"))

    assert isinstance(provider, OpenRouteServiceClient)


async def test_provider_choice_comes_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTING_PROVIDER", "openrouteservice")

    provider = await provider_for(RoutingSettings(_env_file=None))

    assert isinstance(provider, OpenRouteServiceClient)


async def test_built_osrm_client_asks_the_configured_server() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"code": "NoRoute", "message": "No route found"})

    settings = RoutingSettings(_env_file=None, OSRM_BASE_URL="http://osrm.local:5000")
    async with create_routing_http_client(settings, transport=httpx.MockTransport(handle)) as http:
        provider = create_routing_provider(settings, http)
        with pytest.raises(RouteNotFoundError):
            await provider.get_route(ORIGIN, DESTINATION)

    assert [(request.url.host, request.url.port) for request in requests] == [("osrm.local", 5000)]
