import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from support.routing import ScriptedProvider, isolate_routing_environment
from taxi_service.modules.geo.client import create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.mapbox import MapboxClient
from taxi_service.modules.geo.schemas import Coordinates

ORIGIN = Coordinates(longitude=76.92284, latitude=43.26759)
DESTINATION = Coordinates(longitude=76.89231, latitude=43.20164)
TOKEN = "pk.unit-only-not-a-real-token"


@pytest.fixture(autouse=True)
def isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_routing_environment(monkeypatch)


def payload(**changes: Any) -> dict[str, Any]:
    route = {
        "distance": 11799.4,
        "duration": 3600.5,
        "duration_typical": 1500.3,
        "geometry": {
            "type": "LineString",
            "coordinates": [ORIGIN.as_lon_lat(), DESTINATION.as_lon_lat()],
        },
    }
    route.update(changes)
    return {"code": "Ok", "routes": [route]}


@asynccontextmanager
async def adapter(script: ScriptedProvider, **changes: Any) -> AsyncIterator[MapboxClient]:
    options: dict[str, Any] = {"MAPBOX_TOKEN": TOKEN, "max_retries": 0}
    options.update(changes)
    settings = RoutingSettings(_env_file=None, **options)
    async with create_routing_http_client(
        settings, transport=httpx.MockTransport(script.handle)
    ) as http:
        yield MapboxClient.from_settings(settings, http, sleep=script.sleep, clock=script.clock)


async def test_mapbox_uses_traffic_duration_and_lon_lat_geojson(
    caplog: pytest.LogCaptureFixture,
) -> None:
    script = ScriptedProvider(httpx.Response(200, json=payload()))
    with caplog.at_level(logging.INFO, logger="httpx"):
        async with adapter(script) as client:
            result = await client.get_route(ORIGIN, DESTINATION)
    assert (result.duration_s, result.duration_typical_s, result.distance_m) == (3601, 1500, 11799)
    assert result.traffic_mode == "live_or_typical"
    assert result.provider == "mapbox"
    assert result.generated_at is not None
    assert result.route_geometry.coordinates[0] == ORIGIN.as_lon_lat()
    [request] = script.requests
    assert (
        request.url.path
        == "/directions/v5/mapbox/driving-traffic/76.92284,43.26759;76.89231,43.20164"
    )
    assert dict(request.url.params) == {
        "access_token": TOKEN,
        "geometries": "geojson",
        "overview": "full",
        "alternatives": "false",
        "steps": "false",
    }
    assert TOKEN not in caplog.text
    assert "[redacted]" in caplog.text


async def test_missing_typical_does_not_claim_traffic_coverage() -> None:
    async with adapter(
        ScriptedProvider(httpx.Response(200, json=payload(duration_typical=None)))
    ) as client:
        route = await client.get_route(ORIGIN, DESTINATION)
    assert route.traffic_mode == "none"
    assert route.duration_typical_s is None


@pytest.mark.parametrize("status", [401, 403, 400])
async def test_refusal_is_not_retried_or_reflected(status: int) -> None:
    script = ScriptedProvider(httpx.Response(status, json={"message": f"secret: {TOKEN}"}))
    async with adapter(script, max_retries=2) as client:
        with pytest.raises(RoutingProviderError) as error:
            await client.get_route(ORIGIN, DESTINATION)
    assert error.value.reason == "rejected"
    assert len(script.requests) == 1
    assert TOKEN not in str(error.value.details)


@pytest.mark.parametrize("code", ["NoRoute", "NoSegment"])
async def test_no_route_is_explicit(code: str) -> None:
    async with adapter(ScriptedProvider(httpx.Response(200, json={"code": code}))) as client:
        with pytest.raises(RouteNotFoundError):
            await client.get_route(ORIGIN, DESTINATION)


@pytest.mark.parametrize(
    "change",
    [
        {"duration": -1},
        {"duration": "3600"},
        {"duration": float("inf")},
        {"distance": True},
        {"duration_typical": -1},
        {"geometry": {"type": "Point", "coordinates": [76.9, 43.2]}},
    ],
)
async def test_invalid_response_is_not_a_route(change: dict[str, Any]) -> None:
    # json text allows Infinity to exercise finite validation, unlike httpx's JSON encoder.
    import json

    response = httpx.Response(200, text=json.dumps(payload(**change)))
    async with adapter(ScriptedProvider(response)) as client:
        with pytest.raises(RoutingProviderError) as error:
            await client.get_route(ORIGIN, DESTINATION)
    assert error.value.reason == "invalid_response"


@pytest.mark.parametrize("first", [429, 503])
async def test_transient_status_retries_with_budget(first: int) -> None:
    script = ScriptedProvider(
        httpx.Response(first, headers={"Retry-After": "1"}), httpx.Response(200, json=payload())
    )
    async with adapter(script, max_retries=1) as client:
        await client.get_route(ORIGIN, DESTINATION)
    assert len(script.requests) == 2
    assert script.sleeps == [1]


async def test_timeout_has_safe_error() -> None:
    script = ScriptedProvider(httpx.ReadTimeout)
    async with adapter(script) as client:
        with pytest.raises(RoutingProviderError) as error:
            await client.get_route(ORIGIN, DESTINATION)
    assert error.value.reason == "timeout"


async def test_unconfigured_token_never_sends_request() -> None:
    script = ScriptedProvider()
    async with adapter(script, MAPBOX_TOKEN="") as client:
        with pytest.raises(RoutingUnavailableError):
            await client.get_route(ORIGIN, DESTINATION)
    assert not script.requests


def test_mapbox_token_is_read_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAPBOX_TOKEN", f" {TOKEN} ")
    settings = RoutingSettings(_env_file=None, provider="mapbox")
    assert settings.mapbox_token is not None
    assert settings.mapbox_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(settings)
    assert TOKEN not in settings.model_dump_json()
