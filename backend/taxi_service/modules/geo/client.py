import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr

from taxi_service.core.errors import AppError
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
    """HTTP client for the routing provider; the caller owns and closes it.

    The base URL is openrouteservice's; OSRM requests use absolute URLs.
    """
    return httpx.AsyncClient(
        base_url=str(settings.base_url),
        timeout=httpx.Timeout(settings.read_timeout_s, connect=settings.connect_timeout_s),
        transport=transport,
    )


Metric = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retries of one route request; every attempt and pause share ``total_timeout_s``."""

    max_retries: int = 1
    retry_backoff_s: float = 0.5
    max_retry_delay_s: float = 5.0
    total_timeout_s: float = 10.0

    @classmethod
    def from_settings(cls, settings: RoutingSettings) -> "RetryPolicy":
        return cls(
            max_retries=settings.max_retries,
            retry_backoff_s=settings.retry_backoff_s,
            max_retry_delay_s=settings.max_retry_delay_s,
            total_timeout_s=settings.total_timeout_s,
        )

    def delay(self, attempt: int, retry_after_s: float | None) -> float:
        delay = self.retry_backoff_s * 2**attempt if retry_after_s is None else retry_after_s
        return float(min(self.max_retry_delay_s, delay))


@dataclass(frozen=True, slots=True)
class TransientFailure:
    error: AppError
    retry_after_s: float | None = None


Attempt = Callable[[float], Awaitable[RouteResult | TransientFailure]]


async def route_with_retries(
    attempt: Attempt, policy: RetryPolicy, *, sleep: Sleep, clock: Clock
) -> RouteResult:
    """Runs ``attempt(remaining_s)`` until a route, a permanent error or the budget ends."""
    deadline = clock() + policy.total_timeout_s
    retry = 0
    while True:
        outcome = await attempt(deadline - clock())
        if isinstance(outcome, RouteResult):
            return outcome
        reason = outcome.error.details.get("reason", outcome.error.code)
        logger.warning("Routing attempt %d failed: %s", retry + 1, reason)
        delay = policy.delay(retry, outcome.retry_after_s)
        if retry >= policy.max_retries or deadline <= clock() + delay:
            raise outcome.error
        await sleep(delay)
        retry += 1


async def send_within(
    request: Awaitable[httpx.Response],
    remaining_s: float,
    *,
    refused_means_unavailable: bool = False,
) -> httpx.Response | TransientFailure:
    """Awaits ``request`` within the budget left; maps httpx errors to the ADR 0002 contract."""
    try:
        async with asyncio.timeout(remaining_s):
            return await request
    except TimeoutError:
        raise RoutingProviderError("timeout") from None
    except httpx.TimeoutException:
        return TransientFailure(RoutingProviderError("timeout"))
    except httpx.ConnectError:
        if refused_means_unavailable:
            return TransientFailure(RoutingUnavailableError())
        return TransientFailure(RoutingProviderError("connection_error"))
    except httpx.TransportError:
        return TransientFailure(RoutingProviderError("connection_error"))
    except httpx.DecodingError:
        raise RoutingProviderError("invalid_response") from None
    except httpx.RequestError:
        raise RoutingProviderError("rejected") from None


def server_failure(response: httpx.Response) -> TransientFailure | None:
    """429 and 5xx are worth another attempt, after ``Retry-After`` when it gives seconds."""
    status = response.status_code
    if status != httpx.codes.TOO_MANY_REQUESTS and status < httpx.codes.INTERNAL_SERVER_ERROR:
        return None
    reason: ProviderFailure = (
        "rate_limited" if status == httpx.codes.TOO_MANY_REQUESTS else "provider_unavailable"
    )
    error = RoutingProviderError(reason, provider_status=status)
    return TransientFailure(error, _retry_after_seconds(response))


def json_or_none(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def round_metric(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Delay-seconds form of ``Retry-After``; the HTTP-date form falls back to backoff."""
    value = response.headers.get("Retry-After", "").strip()
    return float(value) if value.isdecimal() else None


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

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_key: SecretStr | None,
        retry: RetryPolicy,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        self._http = http_client
        self._api_key = api_key
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
    ) -> "OpenRouteServiceClient":
        return cls(
            http_client,
            api_key=settings.api_key,
            retry=RetryPolicy.from_settings(settings),
            sleep=sleep,
            clock=clock,
        )

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        """Retries timeouts, connection errors, 429 and 5xx within one ``total_timeout_s``."""
        if self._api_key is None:
            raise RoutingUnavailableError()
        body = {"coordinates": [origin.as_lon_lat(), destination.as_lon_lat()]}
        headers = {
            "Authorization": self._api_key.get_secret_value(),
            "Accept": "application/geo+json, application/json",
        }

        async def attempt(remaining_s: float) -> RouteResult | TransientFailure:
            request = self._http.post(DIRECTIONS_PATH, json=body, headers=headers)
            response = await send_within(request, remaining_s)
            if isinstance(response, TransientFailure):
                return response
            return _classify(response)

        return await route_with_retries(attempt, self._retry, sleep=self._sleep, clock=self._clock)


def _classify(response: httpx.Response) -> RouteResult | TransientFailure:
    if response.status_code == httpx.codes.OK:
        return _route_from(response)
    failure = server_failure(response)
    if failure is not None:
        return failure
    raise _refusal(response)


def _route_from(response: httpx.Response) -> RouteResult:
    try:
        feature = _OrsFeatureCollection.model_validate(response.json()).features[0]
    except ValueError:  # JSONDecodeError and pydantic.ValidationError
        raise RoutingProviderError(
            "invalid_response", provider_status=response.status_code
        ) from None
    return RouteResult(
        distance_m=round_metric(feature.properties.summary.distance),
        duration_s=round_metric(feature.properties.summary.duration),
        route_geometry=feature.geometry,
        provider=PROVIDER_NAME,
    )


def _refusal(response: httpx.Response) -> RouteNotFoundError | RoutingProviderError:
    if _ors_error_code(response) in UNREACHABLE_POINT_CODES:
        return RouteNotFoundError()
    return RoutingProviderError("rejected", provider_status=response.status_code)


def _ors_error_code(response: httpx.Response) -> int | None:
    payload = json_or_none(response)
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if type(code) is int else None
