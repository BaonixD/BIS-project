import httpx

from taxi_service.modules.geo.client import OpenRouteServiceClient, RoutingProvider
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.osrm import OsrmClient


def create_routing_provider(
    settings: RoutingSettings, http_client: httpx.AsyncClient
) -> RoutingProvider:
    """The adapter chosen by ``ROUTING_PROVIDER``, on an HTTP client the caller owns."""
    if settings.provider == "openrouteservice":
        return OpenRouteServiceClient.from_settings(settings, http_client)
    return OsrmClient.from_settings(settings, http_client)
