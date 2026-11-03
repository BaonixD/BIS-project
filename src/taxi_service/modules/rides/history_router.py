from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.history_schemas import RideFiltersDep, RideSummary
from taxi_service.modules.rides.queries import RideQueries
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/rides", tags=["rides"])

Participant = Annotated[
    AuthenticatedUser, Depends(require_roles(UserRole.PASSENGER, UserRole.DRIVER))
]


def get_ride_queries(session: DbSession) -> RideQueries:
    return RideQueries(session)


RideQueriesDep = Annotated[RideQueries, Depends(get_ride_queries)]


@router.get("", responses=error_responses(401, 403))
async def list_my_rides(
    user: Participant, queries: RideQueriesDep, page: PageParamsDep, filters: RideFiltersDep
) -> Page[RideSummary]:
    """Ride history, newest first (`created_at DESC, id DESC`).

    A passenger gets their own rides, active ones included; a driver gets the
    rides assigned to them now (a ride they released is no longer theirs).
    Admins get `403 forbidden` and use `GET /admin/rides`. Items omit the
    route geometry: read it with `GET /rides/{ride_id}`.

    Filters combine with AND: `status` (repeatable), `created_from`
    (inclusive) and `created_to` (exclusive), times with a UTC offset.
    Errors: `422 validation_error` (unknown status, time without offset,
    limit outside 1-100); `422 invalid_date_range`.
    """
    result = await queries.history(
        user.id, user.role, filters, limit=page.limit, offset=page.offset
    )
    return RideSummary.page(result, page)
