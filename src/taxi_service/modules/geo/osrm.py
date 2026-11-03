import asyncio
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from taxi_service.modules.geo.client import (
    Clock,
    Metric,
    RetryPolicy,
    Sleep,
    TransientFailure,
    json_or_none,
    round_metric,
    route_with_retries,
    send_within,
    server_failure,
)
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

PROVIDER_NAME = "osrm"
ROUTE_QUERY = {"overview": "full", "geometries": "geojson", "steps": "false"}
# OSRM response codes for points off the road graph or without a drivable path.
UNREACHABLE_CODES = frozenset({"NoRoute", "NoSegment"})


class _OsrmRoute(BaseModel):
    geometry: RouteGeometry
    distance: Metric
    duration: Metric


class _OsrmResponse(BaseModel):
    code: Literal["Ok"]
    routes: list[_OsrmRoute] = Field(min_length=1)


class OsrmClient:
    """OSRM route service adapter for the car profile of a self-hosted server (ADR 0014)."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        base_url: HttpUrl | None,
        retry: RetryPolicy,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        self._retry = retry
        self._sleep = sleep
        self._clock = clock

    @classmethod
    def from_settings(
        cls,
        settings: RoutingSettings,
        http_client: httpx.AsyncClient,
        *,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> "OsrmClient":
        return cls(
            http_client,
            base_url=settings.osrm_base_url,
            retry=RetryPolicy.from_settings(settings),
            sleep=sleep,
            clock=clock,
        )

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        """A refused connection means the server is not running: ``routing_unavailable``."""
        if self._base_url is None:
            raise RoutingUnavailableError()
        url = _route_url(self._base_url, origin, destination)

        async def attempt(remaining_s: float) -> RouteResult | TransientFailure:
            request = self._http.get(url, params=ROUTE_QUERY)
            response = await send_within(request, remaining_s, refused_means_unavailable=True)
            if isinstance(response, TransientFailure):
                return response
            return _classify(response)

        return await route_with_retries(attempt, self._retry, sleep=self._sleep, clock=self._clock)


def _route_url(base_url: HttpUrl, origin: Coordinates, destination: Coordinates) -> str:
    points = ";".join(f"{point.longitude},{point.latitude}" for point in (origin, destination))
    return f"{str(base_url).rstrip('/')}/route/v1/driving/{points}"


def _classify(response: httpx.Response) -> RouteResult | TransientFailure:
    failure = server_failure(response)
    if failure is not None:
        return failure
    payload = json_or_none(response)
    if isinstance(payload, dict) and payload.get("code") in UNREACHABLE_CODES:
        raise RouteNotFoundError()
    if response.status_code != httpx.codes.OK:
        raise RoutingProviderError("rejected", provider_status=response.status_code)
    return _route_from(payload)


def _route_from(payload: Any) -> RouteResult:
    try:
        route = _OsrmResponse.model_validate(payload).routes[0]
    except ValidationError:
        raise RoutingProviderError("invalid_response", provider_status=200) from None
    return RouteResult(
        distance_m=round_metric(route.distance),
        duration_s=round_metric(route.duration),
        route_geometry=route.geometry,
        provider=PROVIDER_NAME,
    )
