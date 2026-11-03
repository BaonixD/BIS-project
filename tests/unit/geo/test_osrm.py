from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from support.routing import HANG, Reply, ScriptedProvider, isolate_routing_environment
from taxi_service.modules.geo.client import create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.osrm import OsrmClient
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

INDUSTRIALNAYA = Coordinates(longitude=76.922840915814348, latitude=43.267596630084)
MEGA_ALMA_ATA = Coordinates(longitude=76.8923175, latitude=43.2016499)
LINE = [[76.922841, 43.267597], [76.94102, 43.26], [76.892318, 43.20165]]


@pytest.fixture(autouse=True)
def _isolate_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_routing_environment(monkeypatch)


def osrm_payload(
    *, distance: Any = 10336.4, duration: Any = 832.6, geometry: Any = None
) -> dict[str, Any]:
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": geometry or {"type": "LineString", "coordinates": LINE},
                "legs": [{"steps": [], "summary": "", "weight": 832.6, "distance": distance}],
                "weight_name": "routability",
                "weight": 832.6,
                "distance": distance,
                "duration": duration,
            }
        ],
        "waypoints": [
            {"hint": "abc", "distance": 3.1, "name": "Индустриальная", "location": LINE[0]},
            {"hint": "def", "distance": 12.0, "name": "", "location": LINE[-1]},
        ],
    }


def ok(payload: dict[str, Any] | None = None) -> httpx.Response:
    return httpx.Response(200, json=payload or osrm_payload())


def osrm_error(status: int, code: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": f"scripted {code}"})


@asynccontextmanager
async def osrm_client(provider: ScriptedProvider, **overrides: Any) -> AsyncIterator[OsrmClient]:
    settings = RoutingSettings(
        _env_file=None, **{"OSRM_BASE_URL": "http://127.0.0.1:5001"} | overrides
    )
    transport = httpx.MockTransport(provider.handle)
    async with create_routing_http_client(settings, transport=transport) as http:
        yield OsrmClient.from_settings(settings, http, sleep=provider.sleep, clock=provider.clock)


async def route(provider: ScriptedProvider, **overrides: Any) -> RouteResult:
    async with osrm_client(provider, **overrides) as client:
        return await client.get_route(INDUSTRIALNAYA, MEGA_ALMA_ATA)


async def test_successful_route_is_normalized_to_route_result() -> None:
    result = await route(ScriptedProvider(ok()))

    assert result == RouteResult(
        distance_m=10336,
        duration_s=833,
        route_geometry=RouteGeometry.model_validate({"type": "LineString", "coordinates": LINE}),
        provider="osrm",
    )


async def test_request_follows_the_route_service_contract() -> None:
    provider = ScriptedProvider(ok())

    await route(provider)

    [request] = provider.requests
    assert request.method == "GET"
    assert request.url.scheme == "http"
    assert request.url.host == "127.0.0.1"
    assert request.url.port == 5001
    assert request.url.path == (
        "/route/v1/driving/76.92284091581435,43.267596630084;76.8923175,43.2016499"
    )
    assert dict(request.url.params) == {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }
    assert "Authorization" not in request.headers


async def test_base_url_path_prefix_is_kept() -> None:
    provider = ScriptedProvider(ok())

    await route(provider, OSRM_BASE_URL="https://routes.example.test/osrm/")

    [request] = provider.requests
    assert str(request.url).startswith(
        "https://routes.example.test/osrm/route/v1/driving/76.92284091581435,"
    )


@pytest.mark.parametrize("base_url", ["", "   "])
async def test_blank_base_url_is_unavailable_without_any_request(base_url: str) -> None:
    provider = ScriptedProvider(ok())

    with pytest.raises(RoutingUnavailableError) as caught:
        await route(provider, OSRM_BASE_URL=base_url)

    assert caught.value.status_code == 503
    assert caught.value.code == "routing_unavailable"
    assert provider.requests == []


@pytest.mark.parametrize(
    "reply",
    [
        osrm_error(400, "NoRoute"),
        osrm_error(400, "NoSegment"),
        osrm_error(200, "NoRoute"),
    ],
    ids=["no_route", "no_segment", "no_route_with_200"],
)
async def test_unreachable_points_are_route_not_found(reply: httpx.Response) -> None:
    provider = ScriptedProvider(reply)

    with pytest.raises(RouteNotFoundError) as caught:
        await route(provider)

    assert caught.value.status_code == 422
    assert caught.value.code == "route_not_found"
    assert len(provider.requests) == 1
    assert provider.sleeps == []


INVALID_RESPONSES = {
    "not_json": httpx.Response(200, text="<html>gateway</html>"),
    "json_not_object": httpx.Response(200, json=[1, 2]),
    "no_code": ok({"routes": osrm_payload()["routes"]}),
    "other_code_with_200": osrm_error(200, "InvalidQuery"),
    "no_routes": ok({"code": "Ok", "routes": []}),
    "negative_distance": ok(osrm_payload(distance=-1.0)),
    "string_duration": ok(osrm_payload(duration="833")),
    "encoded_polyline": ok(osrm_payload(geometry="_p~iF~ps|U_ulLnnqC")),
    "single_position": ok(
        osrm_payload(geometry={"type": "LineString", "coordinates": [[76.9, 43.2]]})
    ),
}


@pytest.mark.parametrize("reply", INVALID_RESPONSES.values(), ids=INVALID_RESPONSES.keys())
async def test_unusable_success_response_is_a_provider_error(reply: httpx.Response) -> None:
    provider = ScriptedProvider(reply)

    with pytest.raises(RoutingProviderError) as caught:
        await route(provider)

    assert caught.value.details == {"reason": "invalid_response", "provider_status": 200}
    assert len(provider.requests) == 1


@pytest.mark.parametrize(
    "reply",
    [
        osrm_error(400, "InvalidQuery"),
        osrm_error(400, "TooBig"),
        osrm_error(400, "InvalidUrl"),
        httpx.Response(404, text="Not Found"),
        httpx.Response(204),
    ],
    ids=["invalid_query", "too_big", "invalid_url", "not_found_html", "no_content"],
)
async def test_other_refusals_are_rejected_without_retry(reply: httpx.Response) -> None:
    provider = ScriptedProvider(reply, ok())

    with pytest.raises(RoutingProviderError) as caught:
        await route(provider)

    assert caught.value.details == {"reason": "rejected", "provider_status": reply.status_code}
    assert len(provider.requests) == 1
    assert provider.sleeps == []


@pytest.mark.parametrize(
    "first_failure",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(503, text="Service Unavailable"),
        httpx.ReadTimeout,
        httpx.ConnectError,
        httpx.RemoteProtocolError,
    ],
    ids=["500", "503", "read_timeout", "connect_error", "protocol_error"],
)
async def test_transient_failure_is_retried_then_succeeds(first_failure: Reply) -> None:
    provider = ScriptedProvider(first_failure, ok())

    result = await route(provider)

    assert result.provider == "osrm"
    assert len(provider.requests) == 2
    assert provider.sleeps == [0.5]
    first, second = provider.requests
    assert first.url == second.url


@pytest.mark.parametrize(
    ("failure", "reason", "provider_status"),
    [
        (httpx.Response(502, text="Bad Gateway"), "provider_unavailable", 502),
        (httpx.ReadTimeout, "timeout", None),
        (httpx.ConnectTimeout, "timeout", None),
        (httpx.RemoteProtocolError, "connection_error", None),
    ],
    ids=["502", "read_timeout", "connect_timeout", "protocol_error"],
)
async def test_bounded_retries_end_in_provider_error(
    failure: Reply, reason: str, provider_status: int | None
) -> None:
    provider = ScriptedProvider(failure, failure, failure, ok())

    with pytest.raises(RoutingProviderError) as caught:
        await route(provider, max_retries=2)

    assert len(provider.requests) == 3
    assert provider.sleeps == [0.5, 1.0]
    assert caught.value.details == {"reason": reason, "provider_status": provider_status}
    assert caught.value.__cause__ is None


async def test_server_that_refuses_connections_is_unavailable() -> None:
    provider = ScriptedProvider(httpx.ConnectError, httpx.ConnectError, ok())

    with pytest.raises(RoutingUnavailableError) as caught:
        await route(provider)

    assert caught.value.status_code == 503
    assert caught.value.code == "routing_unavailable"
    assert caught.value.__cause__ is None
    assert len(provider.requests) == 2


async def test_slow_attempts_and_pauses_share_one_total_budget() -> None:
    failure = httpx.Response(503)
    provider = ScriptedProvider(*[failure] * 6, latency_s=4.0)

    with pytest.raises(RoutingProviderError) as caught:
        await route(provider, max_retries=5, total_timeout_s=10.0)

    assert len(provider.requests) == 3
    assert provider.sleeps == [0.5, 1.0]
    assert caught.value.details == {"reason": "provider_unavailable", "provider_status": 503}


async def test_total_deadline_interrupts_a_hanging_request() -> None:
    provider = ScriptedProvider(HANG, ok())

    with pytest.raises(RoutingProviderError) as caught:
        await route(provider, total_timeout_s=0.05)

    assert caught.value.details == {"reason": "timeout", "provider_status": None}
    assert len(provider.requests) == 1
    assert provider.sleeps == []
