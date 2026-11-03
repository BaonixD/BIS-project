"""Usage: uv run python scripts/routing_smoke.py — one real ORS route; exit 2 = external_pending."""

import asyncio
import sys

from taxi_service.core.errors import AppError
from taxi_service.modules.geo.client import OpenRouteServiceClient, create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.rides.pricing import calculate_fare

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_EXTERNAL_PENDING = 2

ABAY_DOSTYK = Coordinates(longitude=76.9572, latitude=43.2389)
AL_FARABI_ESENTAI = Coordinates(longitude=76.9286, latitude=43.2187)
# Catches swapped lon/lat in the geometry.
ALMATY_LON = (76.6, 77.3)
ALMATY_LAT = (43.0, 43.5)


def _inside_almaty(route: RouteResult) -> bool:
    return all(
        ALMATY_LON[0] <= lon <= ALMATY_LON[1] and ALMATY_LAT[0] <= lat <= ALMATY_LAT[1]
        for lon, lat in route.route_geometry.coordinates
    )


async def main() -> int:
    settings = RoutingSettings()
    if settings.api_key is None:
        print("external_pending: ROUTING_API_KEY is not set; no real route was requested.")
        return EXIT_EXTERNAL_PENDING

    async with create_routing_http_client(settings) as http:
        client = OpenRouteServiceClient.from_settings(settings, http)
        try:
            route = await client.get_route(ABAY_DOSTYK, AL_FARABI_ESENTAI)
        except AppError as error:
            print(f"failed: {error.code} {error.details}", file=sys.stderr)
            return EXIT_FAILED

    if route.distance_m == 0 or not _inside_almaty(route):
        print("failed: route is empty or its geometry is outside Almaty", file=sys.stderr)
        return EXIT_FAILED

    fare = calculate_fare(distance_m=route.distance_m, duration_s=route.duration_s)
    print(
        f"ok: provider={route.provider} distance_m={route.distance_m} "
        f"duration_s={route.duration_s} points={len(route.route_geometry.coordinates)} "
        f"fare={fare.amount_kzt} {fare.currency} ({fare.tariff_version})"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
