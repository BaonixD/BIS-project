from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.history_schemas import RideSummary
from taxi_service.modules.rides.queries import RideFilters, RidePage, RideQueries
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParams, PageParamsDep

router = APIRouter(prefix="/rides", tags=["rides"])

Participant = Annotated[
    AuthenticatedUser, Depends(require_roles(UserRole.PASSENGER, UserRole.DRIVER))
]


def get_ride_queries(session: SessionDep) -> RideQueries:
    return RideQueries(session)


RideQueriesDep = Annotated[RideQueries, Depends(get_ride_queries)]


def summary_page(result: RidePage, page: PageParams) -> Page[RideSummary]:
    return Page(
        items=[RideSummary.build(ride) for ride in result.rides],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@router.get("", responses=error_responses(401, 403))
async def list_my_rides(
    user: Participant, queries: RideQueriesDep, page: PageParamsDep
) -> Page[RideSummary]:
    """Ride history, newest first (`created_at DESC, id DESC`).

    A passenger gets their own rides, active ones included; a driver gets the
    rides assigned to them now (a ride they released is no longer theirs).
    Admins get `403 forbidden` and use `GET /admin/rides`. Items omit the
    route geometry: read it with `GET /rides/{ride_id}`.
    """
    result = await queries.history(
        user.id, user.role, RideFilters(), limit=page.limit, offset=page.offset
    )
    return summary_page(result, page)
