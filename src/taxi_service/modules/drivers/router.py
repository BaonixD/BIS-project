from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.drivers import service
from taxi_service.modules.drivers.schemas import (
    AvailabilityUpdate,
    DriverProfileUpdate,
    DriverResponse,
    LocationUpdate,
)
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/drivers", tags=["drivers"])

DriverUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.DRIVER))]


@router.get("/me", responses=error_responses(401, 403))
async def read_my_driver_profile(user: DriverUser, db: DbSession) -> DriverResponse:
    return DriverResponse.build(user.id, await service.read_driver_profile(db, user.id))


@router.patch("/me", responses=error_responses(401, 403, 409))
async def update_my_driver_profile(
    body: DriverProfileUpdate, user: DriverUser, db: DbSession, clock: ClockDep
) -> DriverResponse:
    profile = await service.update_profile(db, user.id, body, clock=clock)
    return DriverResponse.build(user.id, profile)


@router.put("/me/availability", responses=error_responses(401, 403, 409))
async def set_my_availability(
    body: AvailabilityUpdate, user: DriverUser, db: DbSession, clock: ClockDep
) -> DriverResponse:
    profile = await service.set_availability(db, user.id, body.online, clock=clock)
    return DriverResponse.build(user.id, profile)


@router.put("/me/location", responses=error_responses(401, 403))
async def update_my_location(
    body: LocationUpdate, user: DriverUser, db: DbSession, clock: ClockDep
) -> DriverResponse:
    profile = await service.update_location(db, user.id, body, clock=clock)
    return DriverResponse.build(user.id, profile)
