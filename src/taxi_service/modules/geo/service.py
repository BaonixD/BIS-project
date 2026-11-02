from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.exceptions import RoutePointsIdenticalError
from taxi_service.modules.geo.schemas import Coordinates, RouteResult


async def plan_road_route(
    provider: RoutingProvider, origin: Coordinates, destination: Coordinates
) -> RouteResult:
    """Road route between two different points; routing errors propagate unchanged.

    Await it outside any database transaction: it waits for an external service.
    """
    if origin == destination:
        raise RoutePointsIdenticalError
    return await provider.get_route(origin, destination)
