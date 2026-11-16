import asyncio
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError

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

MAPBOX_URL = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"


class _TokenLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "access_token=" in message:
            record.msg = re.sub(r"([?&]access_token=)[^&\s\"']+", r"\1[redacted]", message)
            record.args = ()
        return True


class _Route(BaseModel):
    geometry: RouteGeometry
    distance: Metric
    duration: Metric
    duration_typical: Metric | None = None


class _Response(BaseModel):
    code: Literal["Ok"]
    routes: list[_Route] = Field(min_length=1)


class MapboxClient:
    """Directions v5 driving-traffic; no token or external message reaches AppError."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        token: SecretStr | None,
        retry: RetryPolicy,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        logger = logging.getLogger("httpx")
        if not any(isinstance(item, _TokenLogFilter) for item in logger.filters):
            logger.addFilter(_TokenLogFilter())
        self._http = http_client
        self._token = token
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
    ) -> "MapboxClient":
        return cls(
            http_client,
            token=settings.mapbox_token,
            retry=RetryPolicy.from_settings(settings),
            sleep=sleep,
            clock=clock,
        )

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        if self._token is None:
            raise RoutingUnavailableError()
        points = ";".join(f"{p.longitude},{p.latitude}" for p in (origin, destination))
        params = {
            "access_token": self._token.get_secret_value(),
            "geometries": "geojson",
            "overview": "full",
            "alternatives": "false",
            "steps": "false",
        }

        async def attempt(remaining_s: float) -> RouteResult | TransientFailure:
            response = await send_within(
                self._http.get(f"{MAPBOX_URL}/{points}", params=params), remaining_s
            )
            if isinstance(response, TransientFailure):
                return response
            return _classify(response)

        return await route_with_retries(attempt, self._retry, sleep=self._sleep, clock=self._clock)


def _classify(response: httpx.Response) -> RouteResult | TransientFailure:
    failure = server_failure(response)
    if failure is not None:
        return failure
    payload = json_or_none(response)
    if (
        response.status_code in (200, 422)
        and isinstance(payload, dict)
        and payload.get("code") in ("NoRoute", "NoSegment")
    ):
        raise RouteNotFoundError()
    if response.status_code != httpx.codes.OK:
        raise RoutingProviderError("rejected", provider_status=response.status_code)
    return _route_from(payload)


def _route_from(payload: Any) -> RouteResult:
    try:
        route = _Response.model_validate(payload).routes[0]
    except ValidationError:
        raise RoutingProviderError("invalid_response", provider_status=200) from None
    return RouteResult(
        distance_m=round_metric(route.distance),
        duration_s=round_metric(route.duration),
        duration_typical_s=(
            round_metric(route.duration_typical) if route.duration_typical is not None else None
        ),
        traffic_mode="live_or_typical" if route.duration_typical is not None else "none",
        generated_at=datetime.now(UTC),
        route_geometry=route.geometry,
        provider="mapbox",
    )
