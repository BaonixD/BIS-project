from fastapi import APIRouter

from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.geo import service
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.geo.schemas import RouteRequest, RouteResult
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/geo", tags=["geo"])


@router.post("/route", responses=error_responses(401, 403, 503))
async def build_route(
    body: RouteRequest, _user: CurrentUser, routing: RoutingProviderDep
) -> RouteResult:
    return await service.plan_road_route(body.origin, body.destination, routing=routing)
