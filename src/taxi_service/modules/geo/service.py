from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.exceptions import RoutePointsIdenticalError
from taxi_service.modules.geo.schemas import Coordinates, RouteResult


async def plan_road_route(
    origin: Coordinates, destination: Coordinates, *, routing: RoutingProvider
) -> RouteResult:
    """Waits for an external service: await it outside any database transaction."""
    if origin == destination:
        raise RoutePointsIdenticalError
    return await routing.get_route(origin, destination)
