import asyncio
import time
from collections import OrderedDict

from taxi_service.modules.geo.client import Clock, RoutingProvider
from taxi_service.modules.geo.exceptions import RoutingProviderError
from taxi_service.modules.geo.schemas import Coordinates, RouteResult

RouteKey = tuple[float, float, float, float]


class CachedRoutingProvider:
    """Bounded exact-coordinate TTL cache, with shared work for concurrent callers."""

    def __init__(
        self,
        provider: RoutingProvider,
        *,
        ttl_s: float = 30,
        capacity: int = 256,
        clock: Clock = time.monotonic,
    ) -> None:
        self.provider = provider
        self.ttl_s = ttl_s
        self.capacity = capacity
        self._clock = clock
        self._values: OrderedDict[RouteKey, tuple[float, RouteResult]] = OrderedDict()
        self._pending: dict[RouteKey, asyncio.Task[RouteResult]] = {}
        self._closed = False

    async def get_route(self, origin: Coordinates, destination: Coordinates) -> RouteResult:
        if self._closed:
            raise RoutingProviderError("provider_unavailable")
        key = (*origin.as_lon_lat(), *destination.as_lon_lat())
        cached = self._values.get(key)
        if cached is not None and self._clock() - cached[0] < self.ttl_s:
            self._values.move_to_end(key)
            return cached[1]
        self._values.pop(key, None)
        task = self._pending.get(key)
        if task is None:
            if len(self._pending) >= self.capacity:
                raise RoutingProviderError("rate_limited")
            task = asyncio.create_task(self._load(key, origin, destination))
            # A disconnected caller must not cancel another caller's route, or leave
            # an unobserved exception if every caller disconnects.
            task.add_done_callback(_observe)
            self._pending[key] = task
        return await asyncio.shield(task)

    async def _load(
        self, key: RouteKey, origin: Coordinates, destination: Coordinates
    ) -> RouteResult:
        try:
            route = await self.provider.get_route(origin, destination)
            self._values[key] = (self._clock(), route)
            self._values.move_to_end(key)
            while len(self._values) > self.capacity:
                self._values.popitem(last=False)
            return route
        finally:
            self._pending.pop(key, None)

    async def aclose(self) -> None:
        self._closed = True
        tasks = list(self._pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._pending.clear()
        self._values.clear()


def _observe(task: asyncio.Task[RouteResult]) -> None:
    if not task.cancelled():
        task.exception()
