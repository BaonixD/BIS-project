import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.drivers.models import ApprovalStatus
from taxi_service.modules.drivers.schemas import AdminDriverResponse
from taxi_service.modules.drivers.service import DriverAdminService
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/admin/drivers", tags=["admin"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.ADMIN))]


def get_driver_admin_service(session: SessionDep, clock: ClockDep) -> DriverAdminService:
    return DriverAdminService(session, clock)


DriverAdminServiceDep = Annotated[DriverAdminService, Depends(get_driver_admin_service)]


@router.get("", responses=error_responses(401, 403))
async def list_drivers(
    _admin: AdminUser,
    service: DriverAdminServiceDep,
    page: PageParamsDep,
    approval_status: Annotated[
        ApprovalStatus | None, Query(description="Only drivers with this status.")
    ] = None,
) -> Page[AdminDriverResponse]:
    """Driver accounts, newest registration first; a driver without a profile is pending."""
    result = await service.list(approval_status, limit=page.limit, offset=page.offset)
    return Page(
        items=[AdminDriverResponse.from_rows(user, profile) for user, profile in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@router.post("/{driver_id}/approve", responses=error_responses(401, 403, 404, 409))
async def approve_driver(
    driver_id: uuid.UUID, admin: AdminUser, service: DriverAdminServiceDep
) -> AdminDriverResponse:
    """Approve a driver with a complete profile and vehicle.

    409 ``driver_profile_incomplete`` lists ``details.missing_fields``. Approving
    an approved driver again returns the existing approval unchanged.
    """
    user, profile = await service.approve(driver_id, admin_id=admin.id)
    return AdminDriverResponse.from_rows(user, profile)
