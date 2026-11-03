import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.errors import violates_unique
from taxi_service.database.session import read_transaction
from taxi_service.modules.drivers.exceptions import (
    DriverNotApprovedError,
    DriverNotFoundError,
    DriverOnActiveRideError,
    DriverProfileIncompleteError,
    PlateNumberTakenError,
    VehicleYearOutOfRangeError,
)
from taxi_service.modules.drivers.models import (
    VEHICLE_MIN_YEAR,
    ApprovalStatus,
    DriverProfile,
    Vehicle,
    missing_fields,
)
from taxi_service.modules.drivers.repository import DriverRepository
from taxi_service.modules.drivers.schemas import DriverProfileUpdate, VehicleInput
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.dispatch import revoke_driver_offers
from taxi_service.modules.rides.service import driver_has_active_ride
from taxi_service.modules.users.models import User

# Changing these after approval needs a new approval; the phone is only a contact.
_IDENTITY_FIELDS = ("full_name", "license_number")
_VEHICLE_FIELDS = ("make", "model", "color", "plate_number", "year")


class DriverService:
    """Commands of a driver on their own profile; callers pass the driver's user id."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._drivers = DriverRepository(session)

    async def get(self, driver_id: uuid.UUID) -> DriverProfile | None:
        async with read_transaction(self._session):
            return await self._drivers.get(driver_id)

    async def update_profile(
        self, driver_id: uuid.UUID, update: DriverProfileUpdate
    ) -> DriverProfile:
        """Apply the sent fields; an identity or vehicle change revokes the approval.

        Not during an active ride (409 ``driver_on_active_ride``): the passenger
        relies on the name, phone and car shown for the ride.
        """
        if update.vehicle is not None:
            self._check_vehicle_year(update.vehicle.year)
        try:
            async with self._session.begin():
                profile = await self._get_or_create(driver_id)
                await self._ensure_no_active_ride(driver_id)
                vehicle = update.vehicle
                if vehicle is not None and await self._drivers.plate_number_taken(
                    vehicle.plate_number, by_other_than=driver_id
                ):
                    raise PlateNumberTakenError
                changed = _apply_identity(profile, update)
                if update.phone is not None:
                    profile.phone = update.phone
                if vehicle is not None:
                    changed = self._apply_vehicle(profile, vehicle) or changed
                if changed and profile.approval_status is ApprovalStatus.APPROVED:
                    _revoke_approval(profile)
                    await revoke_driver_offers(self._session, driver_id, self._clock.now())
                profile.updated_at = self._clock.now()
        except IntegrityError as error:
            # The pre-check above can race with another transaction; the constraint decides.
            if update.vehicle is not None and _plate_number_conflict(error):
                raise PlateNumberTakenError from error
            raise
        return profile

    async def set_availability(self, driver_id: uuid.UUID, *, online: bool) -> DriverProfile | None:
        """Go online (approved, complete drivers only) or offline (always).

        Going offline revokes a pending offer; the dispatch loop then asks the
        next candidate. With an active ride going offline is 409
        ``driver_on_active_ride``: the ride is completed or released first.
        """
        async with self._session.begin():
            profile = await self._drivers.get_for_update(driver_id)
            if not online:
                await self._ensure_no_active_ride(driver_id)
            if online:
                if profile is None or profile.approval_status is not ApprovalStatus.APPROVED:
                    raise DriverNotApprovedError
                if missing := missing_fields(profile):
                    raise DriverProfileIncompleteError(missing)
            if profile is not None and profile.is_online != online:
                profile.is_online = online
                profile.updated_at = self._clock.now()
            if not online:
                await revoke_driver_offers(self._session, driver_id, self._clock.now())
        return profile

    async def update_location(self, driver_id: uuid.UUID, point: Coordinates) -> DriverProfile:
        """Replace the current location; the time is the server's."""
        async with self._session.begin():
            profile = await self._get_or_create(driver_id)
            now = self._clock.now()
            profile.longitude = point.longitude
            profile.latitude = point.latitude
            profile.location_updated_at = now
            profile.updated_at = now
        return profile

    async def _get_or_create(self, driver_id: uuid.UUID) -> DriverProfile:
        """The profile row, inserted on the driver's first write.

        A concurrent first write may insert the row between the lookup and the
        INSERT (possible on PostgreSQL); the savepoint keeps the transaction
        usable and the row that won is used instead.
        """
        profile = await self._drivers.get_for_update(driver_id)
        if profile is not None:
            return profile
        profile = DriverProfile.new(driver_id, self._clock.now())
        try:
            async with self._session.begin_nested():
                await self._drivers.add(profile)
        except IntegrityError:
            existing = await self._drivers.get_for_update(driver_id)
            if existing is None:
                raise
            return existing
        return profile

    async def _ensure_no_active_ride(self, driver_id: uuid.UUID) -> None:
        if await driver_has_active_ride(self._session, driver_id):
            raise DriverOnActiveRideError

    def _check_vehicle_year(self, year: int) -> None:
        newest = self._clock.now().year + 1
        if not VEHICLE_MIN_YEAR <= year <= newest:
            raise VehicleYearOutOfRangeError(VEHICLE_MIN_YEAR, newest)

    def _apply_vehicle(self, profile: DriverProfile, data: VehicleInput) -> bool:
        values = {name: getattr(data, name) for name in _VEHICLE_FIELDS}
        now = self._clock.now()
        if profile.vehicle is None:
            profile.vehicle = Vehicle(driver_id=profile.user_id, updated_at=now, **values)
            return True
        vehicle = profile.vehicle
        if all(getattr(vehicle, name) == value for name, value in values.items()):
            return False
        for name, value in values.items():
            setattr(vehicle, name, value)
        vehicle.updated_at = now
        return True


@dataclass(frozen=True, slots=True)
class DriverPage:
    rows: list[tuple[User, DriverProfile | None]]
    total: int


class DriverAdminService:
    """Admin view of drivers: listing and approval. The caller checks the admin role."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._drivers = DriverRepository(session)

    async def list(self, status: ApprovalStatus | None, *, limit: int, offset: int) -> DriverPage:
        async with read_transaction(self._session):
            rows = await self._drivers.list_drivers(status, limit=limit, offset=offset)
            total = await self._drivers.count_drivers(status)
        return DriverPage(rows=rows, total=total)

    async def approve(
        self, driver_id: uuid.UUID, *, admin_id: uuid.UUID
    ) -> tuple[User, DriverProfile]:
        """Approve a complete driver; approving again returns the first approval unchanged."""
        async with self._session.begin():
            user = await self._drivers.get_driver_user(driver_id)
            if user is None:
                raise DriverNotFoundError
            profile = await self._drivers.get_for_update(driver_id)
            missing = missing_fields(profile)
            if profile is None or missing:
                raise DriverProfileIncompleteError(missing)
            if profile.approval_status is not ApprovalStatus.APPROVED:
                now = self._clock.now()
                profile.approval_status = ApprovalStatus.APPROVED
                profile.approved_at = now
                profile.approved_by = admin_id
                profile.updated_at = now
        return user, profile


def _apply_identity(profile: DriverProfile, update: DriverProfileUpdate) -> bool:
    changed = False
    for name in _IDENTITY_FIELDS:
        value = getattr(update, name)
        if value is not None and value != getattr(profile, name):
            setattr(profile, name, value)
            changed = True
    return changed


def _revoke_approval(profile: DriverProfile) -> None:
    profile.approval_status = ApprovalStatus.PENDING
    profile.approved_at = None
    profile.approved_by = None
    profile.is_online = False


def _plate_number_conflict(error: IntegrityError) -> bool:
    return violates_unique(
        error, constraint="uq_vehicles_plate_number", table="vehicles", column="plate_number"
    )
