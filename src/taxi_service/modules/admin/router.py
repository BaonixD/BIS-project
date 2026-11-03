"""Read-only admin lists (MVP_SPEC §2, §8): no route here changes a user or a ride."""

import dataclasses
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from taxi_service.database.session import DbSession
from taxi_service.modules.admin.schemas import AdminUserResponse
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.history_router import RideQueriesDep
from taxi_service.modules.rides.history_schemas import RideFiltersDep, RideSummary
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.queries import UserQueries
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.ADMIN))]


def get_user_queries(session: DbSession) -> UserQueries:
    return UserQueries(session)


UserQueriesDep = Annotated[UserQueries, Depends(get_user_queries)]


@router.get("/rides", responses=error_responses(401, 403))
async def list_all_rides(
    _admin: AdminUser,
    queries: RideQueriesDep,
    page: PageParamsDep,
    filters: RideFiltersDep,
    passenger_id: Annotated[uuid.UUID | None, Query(description="Only this passenger.")] = None,
    driver_id: Annotated[
        uuid.UUID | None, Query(description="Only rides assigned to this driver now.")
    ] = None,
) -> Page[RideSummary]:
    """Every ride, newest first (`created_at DESC, id DESC`); admin only.

    Filters combine with AND, as in `GET /rides`: `status` (repeatable),
    `created_from` (inclusive), `created_to` (exclusive), plus
    `passenger_id` and `driver_id`. An unknown id gives an empty page.
    Errors: `422 validation_error`; `422 invalid_date_range`.
    """
    scoped = dataclasses.replace(filters, passenger_id=passenger_id, driver_id=driver_id)
    result = await queries.list_rides(scoped, limit=page.limit, offset=page.offset)
    return RideSummary.page(result, page)


@router.get("/users", responses=error_responses(401, 403))
async def list_users(
    _admin: AdminUser,
    queries: UserQueriesDep,
    page: PageParamsDep,
    role: Annotated[UserRole | None, Query(description="Only accounts with this role.")] = None,
) -> Page[AdminUserResponse]:
    """Accounts, newest first (`created_at DESC, id DESC`); admin only.

    Each item has `id`, `username`, `role`, `created_at` and the profile's
    `display_name` (null without one); never passwords, sessions or phones.
    """
    result = await queries.list_users(role, limit=page.limit, offset=page.offset)
    return Page(
        items=[AdminUserResponse.model_validate(row) for row in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )
