from fastapi import APIRouter

from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.geo.schemas import RouteRequest, RouteResult
from taxi_service.modules.geo.service import plan_road_route
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/geo", tags=["geo"])


@router.post("/route", responses=error_responses(401, 403, 503))
async def build_route(
    body: RouteRequest, user: CurrentUser, routing: RoutingProviderDep
) -> RouteResult:
    """Road route between two points from the external provider (openrouteservice).

    Any logged-in role; needs the X-CSRF-Token header. `route_geometry` is a
    GeoJSON LineString of `[longitude, latitude]` positions. No price: that is
    the ride quote.

    Errors: `422 validation_error`; `422 route_points_identical` (origin equals
    destination, the provider is not asked); `422 route_not_found` (no road
    route between the points); `503 routing_unavailable` (no routing key
    configured); `503 routing_provider_error` (provider failed,
    `details.reason`: timeout, connection_error, rate_limited,
    provider_unavailable, rejected or invalid_response).
    """
    return await plan_road_route(routing, body.origin, body.destination)
