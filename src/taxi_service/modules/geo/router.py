from fastapi import APIRouter

from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.geo.schemas import RouteRequest, RouteResult

router = APIRouter(prefix="/geo", tags=["geo"])


@router.post("/route")
async def build_route(
    body: RouteRequest, user: CurrentUser, routing: RoutingProviderDep
) -> RouteResult:
    """Road route from the external provider; no price (see the ride quote)."""
    return await routing.get_route(body.origin, body.destination)
