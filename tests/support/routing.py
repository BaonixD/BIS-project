"""Controlled ``RoutingProvider`` for tests; never used outside them.

Usage with ``create_app(settings, routing_provider=provider)``::

    provider = FakeRoutingProvider()             # 10 km / 25 min -> economy 2200 KZT (edu-v2)
    provider.fail_with(RoutingUnavailableError())  # every next call raises it
    assert provider.calls == [(origin, destination)]
"""

import asyncio
import os

import httpx
import pytest

from taxi_service.core.errors import AppError
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

FAKE_PROVIDER_NAME = "fake"
FAKE_DISTANCE_M = 10_000
FAKE_DURATION_S = 1_500


def isolate_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``ROUTING_*`` value, real key or local OSRM server reaches ``RoutingSettings()``."""
    for name in list(os.environ):
        if name.startswith("ROUTING_"):
            monkeypatch.delenv(name)
    # An empty variable outranks a key or a local OSRM in a developer's .env file.
    monkeypatch.setenv("ROUTING_API_KEY", "")
    monkeypatch.setenv("OSRM_BASE_URL", "")


def fake_route(origin: Coordinates, destination: Coordinates) -> RouteResult:
    """Deterministic route from ``origin`` to ``destination`` through their midpoint."""
    midpoint = (
        (origin.longitude + destination.longitude) / 2,
        (origin.latitude + destination.latitude) / 2,
    )
    return RouteResult(
        distance_m=FAKE_DISTANCE_M,
        duration_s=FAKE_DURATION_S,
        route_geometry=RouteGeometry(
            type="LineString",
            coordinates=(origin.as_lon_lat(), midpoint, destination.as_lon_lat()),
        ),
        provider=FAKE_PROVIDER_NAME,
    )


class FakeRoutingProvider:
    """Returns ``route`` (or :func:`fake_route`), records every call, can raise ``error``."""

    def __init__(self, route: RouteResult | None = None, *, error: AppError | None = None) -> None:
        self.route = route
        self.error = error
        self.calls: list[tuple[Coordinates, Coordinates]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def fail_with(self, error: AppError | None) -> None:
        """Raise ``error`` on every following call; ``None`` returns routes again."""
        self.error = error

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        self.calls.append((origin, destination))
        if self.error is not None:
            raise self.error
        return self.route or fake_route(origin, destination)


Reply = httpx.Response | type[httpx.RequestError]
HANG = "hang"


class ScriptedProvider:
    """Scripted routing provider behind ``httpx.MockTransport``, on a fake clock.

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
