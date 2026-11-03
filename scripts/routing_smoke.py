"""Usage: uv run python scripts/routing_smoke.py — real routes from ROUTING_PROVIDER.

Exit 2 = external_pending: the provider is not configured and nothing was requested.
"""

import asyncio
import sys

from taxi_service.core.errors import AppError
from taxi_service.modules.geo.client import create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.providers import create_routing_provider
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.rides.pricing import calculate_fares

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_EXTERNAL_PENDING = 2

ABAY_DOSTYK = Coordinates(longitude=76.9572, latitude=43.2389)
AL_FARABI_ESENTAI = Coordinates(longitude=76.9286, latitude=43.2187)
# ADR 0014: a correct route turns right onto Raiymbek and makes a U-turn, about 10.3 km.
INDUSTRIALNAYA = Coordinates(longitude=76.922840915814348, latitude=43.267596630084)
MEGA_ALMA_ATA = Coordinates(longitude=76.8923175, latitude=43.2016499)
ROUTES = {
    "Abay/Dostyk -> Esentai": (ABAY_DOSTYK, AL_FARABI_ESENTAI),
    "Industrialnaya -> MEGA Alma-Ata": (INDUSTRIALNAYA, MEGA_ALMA_ATA),
}
# Catches swapped lon/lat in the geometry.
ALMATY_LON = (76.45, 77.35)
ALMATY_LAT = (43.05, 43.45)


def _missing_setting(settings: RoutingSettings) -> str | None:
    if settings.provider == "openrouteservice" and settings.api_key is None:
        return "ROUTING_API_KEY"
    if settings.provider == "osrm" and settings.osrm_base_url is None:
        return "OSRM_BASE_URL"
    return None


def _inside_almaty(route: RouteResult) -> bool:
    return all(
        ALMATY_LON[0] <= lon <= ALMATY_LON[1] and ALMATY_LAT[0] <= lat <= ALMATY_LAT[1]
        for lon, lat in route.route_geometry.coordinates
    )


def _describe(name: str, route: RouteResult) -> str:
    fares = calculate_fares(distance_m=route.distance_m, duration_s=route.duration_s)
    prices = " ".join(f"{tariff.value}={amount}" for tariff, amount in fares.amounts.items())
    return (
        f"ok: {name}: provider={route.provider} distance_m={route.distance_m} "
        f"duration_s={route.duration_s} points={len(route.route_geometry.coordinates)} "
        f"fares: {prices} {fares.currency} ({fares.tariff_version})"
    )


async def main() -> int:
    settings = RoutingSettings()
    missing = _missing_setting(settings)
    if missing is not None:
        print(f"external_pending: {missing} is not set for {settings.provider}; nothing requested.")
        return EXIT_EXTERNAL_PENDING

    async with create_routing_http_client(settings) as http:
        provider = create_routing_provider(settings, http)
        for name, (origin, destination) in ROUTES.items():
            try:
                route = await provider.get_route(origin, destination)
            except AppError as error:
                print(f"failed: {name}: {error.code} {error.details}", file=sys.stderr)
                return EXIT_FAILED
            if route.distance_m == 0 or not _inside_almaty(route):
                print(f"failed: {name}: empty route or geometry outside Almaty", file=sys.stderr)
                return EXIT_FAILED
            print(_describe(name, route))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
