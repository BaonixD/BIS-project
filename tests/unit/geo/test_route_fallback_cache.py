import asyncio

import httpx
import pytest

from support.routing import FakeRoutingProvider, fake_route, isolate_routing_environment
from taxi_service.modules.geo.cache import CachedRoutingProvider
from taxi_service.modules.geo.client import create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import RouteNotFoundError, RoutingProviderError
from taxi_service.modules.geo.fallback import FallbackRoutingProvider
from taxi_service.modules.geo.providers import create_routing_provider
from taxi_service.modules.geo.schemas import Coordinates, RouteResult

A = Coordinates(longitude=76.9, latitude=43.2)
B = Coordinates(longitude=76.95, latitude=43.25)


async def test_fallback_returns_whole_osrm_route_without_traffic() -> None:
    primary = FakeRoutingProvider(error=RoutingProviderError("rejected", provider_status=401))
    backup_route = fake_route(A, B).model_copy(update={"provider": "osrm"})
    backup = FakeRoutingProvider(backup_route)
    route = await FallbackRoutingProvider(primary, backup).get_route(A, B)
    assert route == backup_route
    assert route.traffic_mode == "none"
    assert backup.call_count == 1


async def test_no_route_does_not_trigger_fallback() -> None:
    backup = FakeRoutingProvider()
    with pytest.raises(RouteNotFoundError):
        await FallbackRoutingProvider(
            FakeRoutingProvider(error=RouteNotFoundError()), backup
        ).get_route(A, B)
    assert backup.call_count == 0


async def test_cache_ttl_capacity_direction_and_failed_routes() -> None:
    now = [0.0]
    raw = FakeRoutingProvider()
    cache = CachedRoutingProvider(raw, ttl_s=30, capacity=1, clock=lambda: now[0])
    await cache.get_route(A, B)
    await cache.get_route(A, B)
    assert raw.call_count == 1
    now[0] = 31
    await cache.get_route(A, B)
    assert raw.call_count == 2
    await cache.get_route(B, A)
    await cache.get_route(A, B)
    assert raw.call_count == 4
    now[0] = 62
    raw.fail_with(RoutingProviderError("timeout"))
    for _ in range(2):
        with pytest.raises(RoutingProviderError):
            await cache.get_route(A, B)
    assert raw.call_count == 6
    await cache.aclose()


async def test_concurrent_callers_share_work_and_cancellation_is_isolated() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()

    class Delayed:
        calls = 0

        async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
            self.calls += 1
            entered.set()
            await release.wait()
            return fake_route(origin, destination)

    raw = Delayed()
    cache = CachedRoutingProvider(raw)
    first = asyncio.create_task(cache.get_route(A, B))
    await entered.wait()
    second = asyncio.create_task(cache.get_route(A, B))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert (await second).distance_m == 10000
    assert raw.calls == 1
    await cache.aclose()


async def test_close_cancels_pending_requests() -> None:
    entered = asyncio.Event()

    class Blocked:
        async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
            entered.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    cache = CachedRoutingProvider(Blocked())
    waiting = asyncio.create_task(cache.get_route(A, B))
    await entered.wait()
    await cache.aclose()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    with pytest.raises(RoutingProviderError):
        await cache.get_route(A, B)


async def test_real_wiring_switches_mapbox_to_osrm_without_mixing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_routing_environment(monkeypatch)
    hosts = []

    def handle(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "api.mapbox.com":
            return httpx.Response(401, json={"message": "bad token"})
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 12000,
                        "duration": 1500,
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [A.as_lon_lat(), B.as_lon_lat()],
                        },
                    }
                ],
            },
        )

    settings = RoutingSettings(
        _env_file=None, provider="mapbox", MAPBOX_TOKEN="pk.unit", OSRM_BASE_URL="http://osrm.local"
    )
    async with create_routing_http_client(settings, transport=httpx.MockTransport(handle)) as http:
        provider = create_routing_provider(settings, http)
        assert isinstance(provider, CachedRoutingProvider)
        route = await provider.get_route(A, B)
        assert (route.provider, route.traffic_mode, route.duration_s) == ("osrm", "none", 1500)
        assert hosts == ["api.mapbox.com", "osrm.local"]
        await provider.aclose()
