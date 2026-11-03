import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, or_, select
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
from taxi_service.modules.drivers.schemas import DriverProfileUpdate, VehicleInput
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.dispatch import revoke_driver_offers
from taxi_service.modules.rides.repository import driver_has_active_ride
from taxi_service.modules.users.models import User, UserRole

# Changing these after approval needs a new approval; the phone is only a contact.
_IDENTITY_FIELDS = ("full_name", "license_number")
_VEHICLE_FIELDS = ("make", "model", "color", "plate_number", "year")


class DriverService:
    """Commands of a driver on their own profile; callers pass the driver's user id."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def get(self, driver_id: uuid.UUID) -> DriverProfile | None:
        async with read_transaction(self._session):
            return await get_driver_profile(self._session, driver_id)

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
                if vehicle is not None and await _plate_number_taken(
                    self._session, vehicle.plate_number, by_other_than=driver_id
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
            profile = await _get_profile_for_update(self._session, driver_id)
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
        profile = await _get_profile_for_update(self._session, driver_id)
        if profile is not None:
            return profile
        profile = DriverProfile.new(driver_id, self._clock.now())
        try:
            async with self._session.begin_nested():
                self._session.add(profile)
                await self._session.flush()
        except IntegrityError:
            existing = await _get_profile_for_update(self._session, driver_id)
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

    async def list(self, status: ApprovalStatus | None, *, limit: int, offset: int) -> DriverPage:
        async with read_transaction(self._session):
            rows = await _list_drivers(self._session, status, limit=limit, offset=offset)
            total = await _count_drivers(self._session, status)
        return DriverPage(rows=rows, total=total)

    async def approve(
        self, driver_id: uuid.UUID, *, admin_id: uuid.UUID
    ) -> tuple[User, DriverProfile]:
        """Approve a complete driver; approving again returns the first approval unchanged."""
        async with self._session.begin():
            user = await _get_driver_user(self._session, driver_id)
            if user is None:
                raise DriverNotFoundError
            profile = await _get_profile_for_update(self._session, driver_id)
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


async def get_driver_profile(db: AsyncSession, driver_id: uuid.UUID) -> DriverProfile | None:
    """The profile with its vehicle, or ``None`` before the driver's first write."""
    return await db.get(DriverProfile, driver_id)


async def _get_profile_for_update(db: AsyncSession, driver_id: uuid.UUID) -> DriverProfile | None:
    # NO KEY: FK checks of rides and offers (FOR KEY SHARE) do not wait for it (ADR 0006).
    result = await db.execute(
        select(DriverProfile)
        .where(DriverProfile.user_id == driver_id)
        .with_for_update(of=DriverProfile, key_share=True)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _plate_number_taken(
    db: AsyncSession, plate_number: str, *, by_other_than: uuid.UUID
) -> bool:
    found = await db.scalar(
        select(Vehicle.id).where(
            Vehicle.plate_number == plate_number, Vehicle.driver_id != by_other_than
        )
    )
    return found is not None


async def _get_driver_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id, User.role == UserRole.DRIVER))


async def _list_drivers(
    db: AsyncSession, status: ApprovalStatus | None, *, limit: int, offset: int
) -> list[tuple[User, DriverProfile | None]]:
    rows = await db.execute(
        _drivers_query(status)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(user, profile) for user, profile in rows]


async def _count_drivers(db: AsyncSession, status: ApprovalStatus | None) -> int:
    total = await db.scalar(select(func.count()).select_from(_drivers_query(status).subquery()))
    return total or 0


def _drivers_query(status: ApprovalStatus | None) -> Select[User, DriverProfile]:
    query = (
        select(User, DriverProfile)
        .outerjoin(DriverProfile, DriverProfile.user_id == User.id)
        .where(User.role == UserRole.DRIVER)
    )
    if status is not None:
        query = query.where(_has_status(status))
    return query


def _has_status(status: ApprovalStatus) -> ColumnElement[bool]:
    # A driver without a profile row is pending.
    if status is ApprovalStatus.PENDING:
        return or_(
            DriverProfile.user_id.is_(None),
            DriverProfile.approval_status == ApprovalStatus.PENDING,
        )
    return DriverProfile.approval_status == status
