import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from taxi_service.database.session import DbSession
from taxi_service.modules.admin.schemas import AdminUserResponse
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides import history
from taxi_service.modules.rides.dependencies import RideFiltersDep
from taxi_service.modules.rides.schemas import RideSummary
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.ADMIN))]


@router.get("/rides", responses=error_responses(401, 403))
async def list_all_rides(
    _admin: AdminUser,
    db: DbSession,
    page: PageParamsDep,
    filters: RideFiltersDep,
    passenger_id: Annotated[uuid.UUID | None, Query(description="Only this passenger.")] = None,
    driver_id: Annotated[
        uuid.UUID | None, Query(description="Only rides assigned to this driver now.")
    ] = None,
) -> Page[RideSummary]:
    result = await history.list_all_rides(
        db,
        filters,
        passenger_id=passenger_id,
        driver_id=driver_id,
        limit=page.limit,
        offset=page.offset,
    )
    return RideSummary.page(result, page)


@router.get("/users", responses=error_responses(401, 403))
async def list_users(
    _admin: AdminUser,
    db: DbSession,
    page: PageParamsDep,
    role: Annotated[UserRole | None, Query(description="Only accounts with this role.")] = None,
) -> Page[AdminUserResponse]:
    result = await users_service.list_users(db, role, limit=page.limit, offset=page.offset)
    return Page(
        items=[AdminUserResponse.model_validate(row) for row in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )
