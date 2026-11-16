import asyncio
import logging

from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.exceptions import RoutingProviderError, RoutingUnavailableError
from taxi_service.modules.geo.schemas import Coordinates, RouteResult

logger = logging.getLogger(__name__)


class FallbackRoutingProvider:
    def __init__(
        self, primary: RoutingProvider, fallback: RoutingProvider, *, fallback_timeout_s: float = 3
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.fallback_timeout_s = fallback_timeout_s

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        try:
            return await self.primary.get_route(origin, destination)
        except (RoutingProviderError, RoutingUnavailableError) as error:
            # Never log external URLs, credentials or response bodies.
            logger.warning("Primary routing unavailable (%s); using OSRM", error.code)
        try:
            async with asyncio.timeout(self.fallback_timeout_s):
                return await self.fallback.get_route(origin, destination)
        except TimeoutError:
            raise RoutingProviderError("timeout") from None
