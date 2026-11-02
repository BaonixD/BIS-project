import asyncio
from collections.abc import Awaitable, Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr

from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

Sleep = Callable[[float], Awaitable[None]]

DIRECTIONS_PATH = "/v2/directions/driving-car/geojson"
# ORS routing error codes: 2009 route not found, 2010 point not found.
UNREACHABLE_POINT_CODES = frozenset({2009, 2010})


class RoutingProvider(Protocol):
    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult: ...


def create_routing_http_client(
    settings: RoutingSettings, *, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """HTTP client for the routing provider; the caller owns and closes it."""
    return httpx.AsyncClient(
        base_url=str(settings.base_url),
        timeout=httpx.Timeout(settings.read_timeout_s, connect=settings.connect_timeout_s),
        transport=transport,
    )


Metric = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class _OrsSummary(BaseModel):
    distance: Metric
    duration: Metric


class _OrsProperties(BaseModel):
    summary: _OrsSummary


class _OrsFeature(BaseModel):
    geometry: RouteGeometry
    properties: _OrsProperties


class _OrsFeatureCollection(BaseModel):
    features: list[_OrsFeature] = Field(min_length=1)


class OpenRouteServiceClient:
    """openrouteservice Directions adapter for the ``driving-car`` profile."""

    PROVIDER = "openrouteservice"

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_key: SecretStr | None,
        max_retries: int = 2,
        retry_backoff_s: float = 0.5,
        max_retry_delay_s: float = 5.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = http_client
        self._api_key = api_key

    @classmethod
    def from_settings(
        cls,
        settings: RoutingSettings,
        http_client: httpx.AsyncClient,
        *,
        sleep: Sleep = asyncio.sleep,
    ) -> "OpenRouteServiceClient":
        return cls(http_client, api_key=settings.api_key, sleep=sleep)

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        if self._api_key is None:
            raise RoutingUnavailableError
        response = await self._http.post(
            DIRECTIONS_PATH,
            json={"coordinates": [origin.as_lon_lat(), destination.as_lon_lat()]},
            headers={
                "Authorization": self._api_key.get_secret_value(),
                "Accept": "application/geo+json, application/json",
            },
        )
        if response.status_code != httpx.codes.OK:
            raise _refusal(response)
        return self._parse_route(response)

    def _parse_route(self, response: httpx.Response) -> RouteResult:
        try:
            payload = response.json()
            feature = _OrsFeatureCollection.model_validate(payload).features[0]
        except ValueError:
            # Covers JSONDecodeError and pydantic.ValidationError.
            raise RoutingProviderError(
                "invalid_response", provider_status=response.status_code
            ) from None
        return RouteResult(
            distance_m=_round_metric(feature.properties.summary.distance),
            duration_s=_round_metric(feature.properties.summary.duration),
            route_geometry=feature.geometry,
            provider=self.PROVIDER,
        )


def _refusal(response: httpx.Response) -> RouteNotFoundError | RoutingProviderError:
    if _ors_error_code(response) in UNREACHABLE_POINT_CODES:
        return RouteNotFoundError()
    return RoutingProviderError("rejected", provider_status=response.status_code)


def _ors_error_code(response: httpx.Response) -> int | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if type(code) is int else None


def _round_metric(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
