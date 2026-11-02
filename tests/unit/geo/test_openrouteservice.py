import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from taxi_service.modules.geo.client import OpenRouteServiceClient, create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

TEST_KEY = "eyJ-test-routing-key-7f3a"
ORIGIN = Coordinates(longitude=76.9572, latitude=43.2389)
DESTINATION = Coordinates(longitude=76.9286, latitude=43.2187)
LINE = [[76.957247, 43.238911], [76.941002, 43.229514], [76.928612, 43.218701]]

Reply = httpx.Response | type[httpx.RequestError]


@pytest.fixture(autouse=True)
def _isolate_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("ROUTING_"):
            monkeypatch.delenv(name)


HANG = "hang"


class FakeProvider:
    """Scripted openrouteservice on a fake clock.

    Replays replies in order, records requests and sleeps; each request costs
    ``latency_s`` and each sleep advances the clock, so no real time passes.
    ``HANG`` blocks the request for 1 s of real time unless a deadline cancels it.
    """

    def __init__(self, *replies: Reply | str, latency_s: float = 0.0) -> None:
        self._replies = list(replies)
        self._latency_s = latency_s
        self.now = 0.0
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.now += self._latency_s
        reply = self._replies.pop(0)
        if isinstance(reply, httpx.Response):
            return reply
        if reply == HANG:
            # A slow provider that only gives up after 1 s of real time.
            await asyncio.sleep(1.0)
            raise httpx.ReadTimeout("scripted slow provider", request=request)
        assert not isinstance(reply, str)
        raise reply("scripted transport failure", request=request)

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def ors_payload(
    *, distance: Any = 4120.4, duration: Any = 610.6, geometry: Any = None
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "bbox": [76.928612, 43.218701, 76.957247, 43.238911],
        "features": [
            {
                "type": "Feature",
                "bbox": [76.928612, 43.218701, 76.957247, 43.238911],
                "properties": {
                    "segments": [{"distance": distance, "duration": duration, "steps": []}],
                    "summary": {"distance": distance, "duration": duration},
                    "way_points": [0, 2],
                },
                "geometry": geometry or {"type": "LineString", "coordinates": LINE},
            }
        ],
        "metadata": {"attribution": "openrouteservice.org | OpenStreetMap contributors"},
    }


def ok(payload: dict[str, Any] | None = None) -> httpx.Response:
    return httpx.Response(200, json=payload or ors_payload())


@asynccontextmanager
async def ors_client(
    provider: FakeProvider, *, api_key: str | None = TEST_KEY, **overrides: Any
) -> AsyncIterator[OpenRouteServiceClient]:
    settings = RoutingSettings(_env_file=None, api_key=api_key, **overrides)
    transport = httpx.MockTransport(provider.handle)
    async with create_routing_http_client(settings, transport=transport) as http:
        yield OpenRouteServiceClient.from_settings(
            settings, http, sleep=provider.sleep, clock=provider.clock
        )


async def test_successful_route_is_normalized_to_route_result() -> None:
    provider = FakeProvider(ok())

    async with ors_client(provider) as client:
        route = await client.get_route(ORIGIN, DESTINATION)

    assert route == RouteResult(
        distance_m=4120,
        duration_s=611,
        route_geometry=RouteGeometry.model_validate({"type": "LineString", "coordinates": LINE}),
        provider="openrouteservice",
    )
    assert type(route.distance_m) is int
    assert type(route.duration_s) is int


async def test_request_follows_directions_geojson_contract() -> None:
    provider = FakeProvider(ok())

    async with ors_client(provider) as client:
        await client.get_route(ORIGIN, DESTINATION)

    [request] = provider.requests
    assert request.method == "POST"
    assert request.url == "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    assert request.headers["Authorization"] == TEST_KEY
    assert json.loads(request.content) == {"coordinates": [[76.9572, 43.2389], [76.9286, 43.2187]]}


async def test_fractional_metrics_round_half_up() -> None:
    provider = FakeProvider(ok(ors_payload(distance=4120.5, duration=610.49)))

    async with ors_client(provider) as client:
        route = await client.get_route(ORIGIN, DESTINATION)

    assert (route.distance_m, route.duration_s) == (4121, 610)


async def test_integer_metrics_are_accepted() -> None:
    provider = FakeProvider(ok(ors_payload(distance=4120, duration=611)))

    async with ors_client(provider) as client:
        route = await client.get_route(ORIGIN, DESTINATION)

    assert (route.distance_m, route.duration_s) == (4120, 611)


async def test_http_client_uses_configured_base_url_and_timeouts() -> None:
    settings = RoutingSettings(
        _env_file=None,
        base_url="https://ors.example.test",
        connect_timeout_s=1.5,
        read_timeout_s=4.0,
    )

    async with create_routing_http_client(settings) as http:
        assert http.base_url == "https://ors.example.test/"
        assert http.timeout == httpx.Timeout(4.0, connect=1.5)


@pytest.mark.parametrize("api_key", [None, ""])
async def test_missing_key_fails_without_any_request(api_key: str | None) -> None:
    provider = FakeProvider(ok())

    async with ors_client(provider, api_key=api_key) as client:
        with pytest.raises(RoutingUnavailableError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert provider.requests == []
    assert provider.sleeps == []
    assert caught.value.status_code == 503
    assert caught.value.code == "routing_unavailable"


INVALID_RESPONSES = {
    "not_json": httpx.Response(200, text="<html>gateway</html>"),
    "json_not_object": httpx.Response(200, json=[1, 2]),
    "nan_literal": httpx.Response(200, text=json.dumps(ors_payload()).replace("4120.4", "NaN")),
    "no_features": ok({"type": "FeatureCollection", "features": []}),
    "no_summary": ok(
        {"features": [{"geometry": {"type": "LineString", "coordinates": LINE}, "properties": {}}]}
    ),
    "negative_distance": ok(ors_payload(distance=-5.0)),
    "negative_duration": ok(ors_payload(duration=-1)),
    "string_distance": ok(ors_payload(distance="4120")),
    "bool_duration": ok(ors_payload(duration=True)),
    "point_geometry": ok(ors_payload(geometry={"type": "Point", "coordinates": [76.9, 43.2]})),
    "single_position": ok(
        ors_payload(geometry={"type": "LineString", "coordinates": [[76.9, 43.2]]})
    ),
    "lat_lon_swapped": ok(
        ors_payload(geometry={"type": "LineString", "coordinates": [[43.2, 176.9], [43.2, 76.9]]})
    ),
}


@pytest.mark.parametrize("reply", INVALID_RESPONSES.values(), ids=INVALID_RESPONSES.keys())
async def test_unusable_success_response_is_a_provider_error(reply: httpx.Response) -> None:
    provider = FakeProvider(reply)

    async with ors_client(provider) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.status_code == 503
    assert caught.value.code == "routing_provider_error"
    assert caught.value.details == {"reason": "invalid_response", "provider_status": 200}
    assert len(provider.requests) == 1


def ors_error(status: int, code: int, message: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"error": {"code": code, "message": message}, "info": {"engine": {"version": "9"}}},
    )


@pytest.mark.parametrize(
    "reply",
    [
        ors_error(404, 2010, "Could not find routable point within a radius of 350.0 meters."),
        ors_error(404, 2009, "Route could not be found - Unable to find a route."),
        ors_error(400, 2010, "Could not find point 1: 76.9286 43.2187 within a radius of 350."),
    ],
    ids=["point_not_routable", "route_not_found", "point_not_found_400"],
)
async def test_unreachable_points_are_route_not_found(reply: httpx.Response) -> None:
    provider = FakeProvider(reply)

    async with ors_client(provider) as client:
        with pytest.raises(RouteNotFoundError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.status_code == 422
    assert caught.value.code == "route_not_found"
    assert len(provider.requests) == 1


@pytest.mark.parametrize(
    "reply",
    [
        ors_error(400, 2004, "Request parameters exceed the server configuration limits."),
        httpx.Response(401, json={"error": "Authorization field missing"}),
        httpx.Response(403, json={"error": "Access to this API has been disallowed"}),
        httpx.Response(404, text="Not Found"),
        httpx.Response(301, headers={"Location": "https://elsewhere.test"}),
    ],
    ids=[
        "limits_exceeded",
        "unauthorized",
        "forbidden_or_daily_quota",
        "not_found_html",
        "redirect",
    ],
)
async def test_other_refusals_are_not_retried(reply: httpx.Response) -> None:
    provider = FakeProvider(reply)

    async with ors_client(provider) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.details == {"reason": "rejected", "provider_status": reply.status_code}
    assert len(provider.requests) == 1
    assert provider.sleeps == []


async def test_provider_error_never_echoes_the_key() -> None:
    provider = FakeProvider(httpx.Response(403, json={"error": f"Key {TEST_KEY} is not valid"}))

    async with ors_client(provider) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    exposed = [str(caught.value), repr(caught.value), caught.value.message]
    exposed.append(json.dumps(caught.value.details))
    assert all(TEST_KEY not in text for text in exposed)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (
            httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(b"not gzip")
            ),
            "invalid_response",
        ),
        (httpx.DecodingError, "invalid_response"),
        (httpx.TooManyRedirects, "rejected"),
        (httpx.RequestError, "rejected"),
    ],
    ids=["corrupt_gzip_body", "decoding_error", "too_many_redirects", "other_request_error"],
)
async def test_non_transport_request_errors_are_provider_errors_without_retry(
    reply: Reply, reason: str
) -> None:
    provider = FakeProvider(reply, ok())

    async with ors_client(provider) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.details == {"reason": reason, "provider_status": None}
    assert caught.value.__cause__ is None
    assert len(provider.requests) == 1
    assert provider.sleeps == []


@pytest.mark.parametrize(
    "first_failure",
    [
        httpx.Response(429, json={"error": "Rate Limit Exceeded"}),
        httpx.Response(500, json={"error": {"code": 2099, "message": "Unknown internal error"}}),
        httpx.Response(502, text="Bad Gateway"),
        httpx.Response(503, text="Service Unavailable"),
        httpx.ReadTimeout,
        httpx.ConnectError,
    ],
    ids=["429", "500", "502", "503", "read_timeout", "connect_error"],
)
async def test_transient_failure_is_retried_then_succeeds(first_failure: Reply) -> None:
    provider = FakeProvider(first_failure, ok())

    async with ors_client(provider) as client:
        route = await client.get_route(ORIGIN, DESTINATION)

    assert route.distance_m == 4120
    assert len(provider.requests) == 2
    assert provider.sleeps == [0.5]
    first, second = provider.requests
    assert first.content == second.content
    assert second.headers["Authorization"] == TEST_KEY


@pytest.mark.parametrize(
    ("failure", "reason", "provider_status"),
    [
        (httpx.Response(429, json={"error": "Rate Limit Exceeded"}), "rate_limited", 429),
        (httpx.Response(500, text="Internal Server Error"), "provider_unavailable", 500),
        (httpx.Response(503, text="Service Unavailable"), "provider_unavailable", 503),
        (httpx.ReadTimeout, "timeout", None),
        (httpx.ConnectTimeout, "timeout", None),
        (httpx.ConnectError, "connection_error", None),
    ],
    ids=["429", "500", "503", "read_timeout", "connect_timeout", "connect_error"],
)
async def test_retries_are_bounded_and_end_in_provider_error(
    failure: Reply, reason: str, provider_status: int | None
) -> None:
    provider = FakeProvider(failure, failure, failure, ok())

    async with ors_client(provider, max_retries=2) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert len(provider.requests) == 3
    assert provider.sleeps == [0.5, 1.0]
    assert caught.value.status_code == 503
    assert caught.value.details == {"reason": reason, "provider_status": provider_status}
    assert TEST_KEY not in str(caught.value)
    assert caught.value.__cause__ is None


async def test_zero_retries_means_a_single_attempt() -> None:
    provider = FakeProvider(httpx.Response(503), ok())

    async with ors_client(provider, max_retries=0) as client:
        with pytest.raises(RoutingProviderError):
            await client.get_route(ORIGIN, DESTINATION)

    assert len(provider.requests) == 1
    assert provider.sleeps == []


async def test_backoff_grows_exponentially_up_to_the_cap() -> None:
    failure = httpx.Response(503)
    provider = FakeProvider(failure, failure, failure, failure)

    async with ors_client(
        provider, max_retries=3, retry_backoff_s=2.0, max_retry_delay_s=3.0
    ) as client:
        with pytest.raises(RoutingProviderError):
            await client.get_route(ORIGIN, DESTINATION)

    assert len(provider.requests) == 4
    assert provider.sleeps == [2.0, 3.0, 3.0]


@pytest.mark.parametrize(
    ("status", "retry_after", "expected_sleep"),
    [
        (429, "2", 2.0),
        (503, "1", 1.0),
        (429, "0", 0.0),
        (429, "120", 5.0),
        (429, "soon", 0.5),
        (429, "-3", 0.5),
        (503, "Wed, 21 Oct 2015 07:28:00 GMT", 0.5),
    ],
    ids=["seconds", "seconds_on_503", "zero", "capped", "garbage", "negative", "http_date"],
)
async def test_retry_after_seconds_are_honoured_up_to_the_cap(
    status: int, retry_after: str, expected_sleep: float
) -> None:
    provider = FakeProvider(httpx.Response(status, headers={"Retry-After": retry_after}), ok())

    async with ors_client(provider) as client:
        await client.get_route(ORIGIN, DESTINATION)

    assert provider.sleeps == [expected_sleep]


async def test_pause_past_the_total_deadline_fails_now() -> None:
    rate_limited = httpx.Response(429, headers={"Retry-After": "5"})
    provider = FakeProvider(rate_limited, ok())

    async with ors_client(provider, max_retries=3, total_timeout_s=3.0) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.details == {"reason": "rate_limited", "provider_status": 429}
    assert len(provider.requests) == 1
    assert provider.sleeps == []


async def test_slow_attempts_and_pauses_share_one_total_budget() -> None:
    failure = httpx.Response(503)
    provider = FakeProvider(*[failure] * 6, latency_s=4.0)

    async with ors_client(provider, max_retries=5, total_timeout_s=10.0) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    # t=4 fail, pause to 4.5, t=8.5 fail, pause to 9.5, t=13.5 fail; a 2 s pause is over budget.
    assert len(provider.requests) == 3
    assert provider.sleeps == [0.5, 1.0]
    assert caught.value.details == {"reason": "provider_unavailable", "provider_status": 503}


async def test_total_deadline_interrupts_a_hanging_request() -> None:
    provider = FakeProvider(HANG, ok())

    async with ors_client(provider, total_timeout_s=0.05) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    assert caught.value.details == {"reason": "timeout", "provider_status": None}
    assert caught.value.__cause__ is None
    assert len(provider.requests) == 1
    assert provider.sleeps == []


async def test_key_never_reaches_logs_across_retries_and_final_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    echo = httpx.Response(503, json={"error": f"bad key {TEST_KEY}"})
    provider = FakeProvider(echo, httpx.ReadTimeout, httpx.Response(429))

    async with ors_client(provider, max_retries=2) as client:
        with pytest.raises(RoutingProviderError) as caught:
            await client.get_route(ORIGIN, DESTINATION)

    adapter_records = [r for r in caplog.records if r.name == "taxi_service.modules.geo.client"]
    assert len(adapter_records) == 3
    assert TEST_KEY not in caplog.text
    assert all(TEST_KEY not in repr(vars(record)) for record in caplog.records)
    error = caught.value
    exposed = [str(error), repr(error), error.message, json.dumps(error.details)]
    assert all(TEST_KEY not in text for text in exposed)


async def test_client_repr_does_not_expose_key() -> None:
    async with ors_client(FakeProvider()) as client:
        assert TEST_KEY not in repr(client)
        assert TEST_KEY not in repr(vars(client))
