from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.drivers.schemas import (
    AvailabilityUpdate,
    DriverProfileUpdate,
    DriverResponse,
    LocationUpdate,
)
from taxi_service.modules.drivers.service import DriverService
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/drivers", tags=["drivers"])

DriverUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.DRIVER))]


def get_driver_service(session: DbSession, clock: ClockDep) -> DriverService:
    return DriverService(session, clock)


DriverServiceDep = Annotated[DriverService, Depends(get_driver_service)]


@router.get("/me", responses=error_responses(401, 403))
async def read_my_driver_profile(user: DriverUser, drivers: DriverServiceDep) -> DriverResponse:
    """The driver's own profile, vehicle, approval, availability and location."""
    return DriverResponse.build(user.id, await drivers.get(user.id))


@router.patch("/me", responses=error_responses(401, 403, 409))
async def update_my_driver_profile(
    body: DriverProfileUpdate, user: DriverUser, drivers: DriverServiceDep
) -> DriverResponse:
    """Change profile fields and/or replace the vehicle.

    409 ``plate_number_taken`` if another driver has the plate. Changing the
    name, licence or vehicle of an approved driver returns them to ``pending``
    and offline until an admin approves again; the phone can change freely.
    """
    return DriverResponse.build(user.id, await drivers.update_profile(user.id, body))


@router.put("/me/availability", responses=error_responses(401, 403, 409))
async def set_my_availability(
    body: AvailabilityUpdate, user: DriverUser, drivers: DriverServiceDep
) -> DriverResponse:
    """Go online or offline. Online needs admin approval (409 ``driver_not_approved``)."""
    return DriverResponse.build(
        user.id, await drivers.set_availability(user.id, online=body.online)
    )


@router.put("/me/location", responses=error_responses(401, 403))
async def update_my_location(
    body: LocationUpdate, user: DriverUser, drivers: DriverServiceDep
) -> DriverResponse:
    """Replace the current position; ``location_updated_at`` is the server time."""
    return DriverResponse.build(user.id, await drivers.update_location(user.id, body))
