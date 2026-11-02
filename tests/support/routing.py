"""Controlled ``RoutingProvider`` for tests; never used outside them.

Usage with ``create_app(settings, routing_provider=provider)``::

    provider = FakeRoutingProvider()             # 10 km / 25 min -> 2200 KZT (edu-v1)
    provider.fail_with(RoutingUnavailableError())  # every next call raises it
    assert provider.calls == [(origin, destination)]
"""

from taxi_service.core.errors import AppError
from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

FAKE_PROVIDER_NAME = "fake"
FAKE_DISTANCE_M = 10_000
FAKE_DURATION_S = 1_500


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
