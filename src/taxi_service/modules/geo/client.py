import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr

from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.exceptions import (
    ProviderFailure,
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]

PROVIDER_NAME = "openrouteservice"
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


@dataclass(frozen=True, slots=True)
class _TransientFailure:
    error: RoutingProviderError
    retry_after_s: float | None = None


class OpenRouteServiceClient:
    """openrouteservice Directions adapter for the ``driving-car`` profile."""

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
        self._max_retries = max_retries
        self._retry_backoff_s = retry_backoff_s
        self._max_retry_delay_s = max_retry_delay_s
        self._sleep = sleep

    @classmethod
    def from_settings(
        cls,
        settings: RoutingSettings,
        http_client: httpx.AsyncClient,
        *,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> "OpenRouteServiceClient":
        return cls(
            http_client,
            api_key=settings.api_key,
            max_retries=settings.max_retries,
            retry_backoff_s=settings.retry_backoff_s,
            max_retry_delay_s=settings.max_retry_delay_s,
            sleep=sleep,
        )

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        """Road route between two points; raises a routing ``AppError`` on failure.

        Only timeouts, connection errors, 429 and 5xx are retried, at most
        ``max_retries`` times; directions requests have no side effects.
        """
        if self._api_key is None:
            raise RoutingUnavailableError
        body = {"coordinates": [origin.as_lon_lat(), destination.as_lon_lat()]}
        headers = {
            "Authorization": self._api_key.get_secret_value(),
            "Accept": "application/geo+json, application/json",
        }
        attempt = 0
        while True:
            outcome = await self._attempt(body, headers)
            if isinstance(outcome, RouteResult):
                return outcome
            logger.warning("Routing attempt %d failed: %s", attempt + 1, outcome.error.reason)
            if attempt >= self._max_retries:
                raise outcome.error
            await self._sleep(self._retry_delay(attempt, outcome.retry_after_s))
            attempt += 1

    async def _attempt(
        self, body: Mapping[str, object], headers: Mapping[str, str]
    ) -> RouteResult | _TransientFailure:
        try:
            response = await self._http.post(DIRECTIONS_PATH, json=body, headers=headers)
        except httpx.TimeoutException:
            return _TransientFailure(RoutingProviderError("timeout"))
        except httpx.TransportError:
            return _TransientFailure(RoutingProviderError("connection_error"))
        except httpx.DecodingError:
            raise RoutingProviderError("invalid_response") from None
        except httpx.RequestError:
            raise RoutingProviderError("rejected") from None
        return _classify(response)

    def _retry_delay(self, attempt: int, retry_after_s: float | None) -> float:
        delay = self._retry_backoff_s * 2**attempt if retry_after_s is None else retry_after_s
        return float(min(self._max_retry_delay_s, delay))


def _classify(response: httpx.Response) -> RouteResult | _TransientFailure:
    """A route, a retryable failure, or a raised final error for one provider response."""
    status = response.status_code
    if status == httpx.codes.OK:
        return _route_from(response)
    if status == httpx.codes.TOO_MANY_REQUESTS or status >= httpx.codes.INTERNAL_SERVER_ERROR:
        reason: ProviderFailure = (
            "rate_limited" if status == httpx.codes.TOO_MANY_REQUESTS else "provider_unavailable"
        )
        error = RoutingProviderError(reason, provider_status=status)
        return _TransientFailure(error, _retry_after_seconds(response))
    raise _refusal(response)


def _route_from(response: httpx.Response) -> RouteResult:
    try:
        feature = _OrsFeatureCollection.model_validate(response.json()).features[0]
    except ValueError:
        # Covers JSONDecodeError and pydantic.ValidationError.
        raise RoutingProviderError(
            "invalid_response", provider_status=response.status_code
        ) from None
    return RouteResult(
        distance_m=_round_metric(feature.properties.summary.distance),
        duration_s=_round_metric(feature.properties.summary.duration),
        route_geometry=feature.geometry,
        provider=PROVIDER_NAME,
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Delay-seconds form of ``Retry-After``; the HTTP-date form falls back to backoff."""
    value = response.headers.get("Retry-After", "").strip()
    return float(value) if value.isdecimal() else None


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
