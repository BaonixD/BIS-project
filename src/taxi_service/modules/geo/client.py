import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
from pydantic import SecretStr

from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.schemas import Coordinates, RouteResult

Sleep = Callable[[float], Awaitable[None]]


class RoutingProvider(Protocol):
    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult: ...


def create_routing_http_client(
    settings: RoutingSettings, *, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport)


class OpenRouteServiceClient:
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
        raise NotImplementedError
