import uuid
from dataclasses import dataclass
from datetime import datetime

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
from taxi_service.modules.rides import service as rides_service
from taxi_service.modules.rides.dispatch import revoke_driver_offers
from taxi_service.modules.rides.tariffs import Tariff, tariffs_above
from taxi_service.modules.users.models import User, UserRole

# Changing these after approval needs a new approval; the phone is only a contact.
_IDENTITY_FIELDS = ("full_name", "license_number")
_VEHICLE_FIELDS = ("make", "model", "color", "plate_number", "year")


async def read_driver_profile(db: AsyncSession, driver_id: uuid.UUID) -> DriverProfile | None:
    async with read_transaction(db):
        return await get_driver_profile(db, driver_id)


async def update_profile(
    db: AsyncSession, driver_id: uuid.UUID, update: DriverProfileUpdate, *, clock: Clock
) -> DriverProfile:
    """An identity or vehicle change of an approved driver revokes the approval."""
    if update.vehicle is not None:
        _check_vehicle_year(update.vehicle.year, newest=clock.now().year + 1)
    try:
        async with db.begin():
            now = clock.now()
            profile = await _get_or_create_profile(db, driver_id, now)
            # The passenger relies on the name, phone and car shown for the ride.
            await _ensure_no_active_ride(db, driver_id)
            vehicle = update.vehicle
            if vehicle is not None and await _plate_number_taken(
                db, vehicle.plate_number, by_other_than=driver_id
            ):
                raise PlateNumberTakenError
            changed = _apply_identity(profile, update)
            if update.phone is not None:
                profile.phone = update.phone
            if vehicle is not None:
                changed = _apply_vehicle(profile, vehicle, now) or changed
            if changed and profile.approval_status is ApprovalStatus.APPROVED:
                _revoke_approval(profile)
                await revoke_driver_offers(db, driver_id, now)
            profile.updated_at = now
    except IntegrityError as error:
        # The pre-check above can race with another transaction; the constraint decides.
        if update.vehicle is not None and _plate_number_conflict(error):
            raise PlateNumberTakenError from error
        raise
    return profile


async def set_availability(
    db: AsyncSession, driver_id: uuid.UUID, online: bool, *, clock: Clock
) -> DriverProfile | None:
    """Going offline revokes a pending offer; the dispatch loop asks the next candidate."""
    async with db.begin():
        profile = await _get_profile_for_update(db, driver_id)
        if online:
            _ensure_can_go_online(profile)
        else:
            await _ensure_no_active_ride(db, driver_id)
        if profile is not None and profile.is_online != online:
            profile.is_online = online
            profile.updated_at = clock.now()
        if not online:
            await revoke_driver_offers(db, driver_id, clock.now())
    return profile


async def update_location(
    db: AsyncSession, driver_id: uuid.UUID, location: Coordinates, *, clock: Clock
) -> DriverProfile:
    async with db.begin():
        now = clock.now()
        profile = await _get_or_create_profile(db, driver_id, now)
        profile.longitude = location.longitude
        profile.latitude = location.latitude
        profile.location_updated_at = now
        profile.updated_at = now
    return profile


async def _get_or_create_profile(
    db: AsyncSession, driver_id: uuid.UUID, now: datetime
) -> DriverProfile:
    # A concurrent first write may insert the row first (PostgreSQL); the savepoint keeps it usable.
    profile = await _get_profile_for_update(db, driver_id)
    if profile is not None:
        return profile
    profile = DriverProfile.new(driver_id, now)
    try:
        async with db.begin_nested():
            db.add(profile)
            await db.flush()
    except IntegrityError:
        existing = await _get_profile_for_update(db, driver_id)
        if existing is None:
            raise
        return existing
    return profile


async def _ensure_no_active_ride(db: AsyncSession, driver_id: uuid.UUID) -> None:
    if await rides_service.driver_has_active_ride(db, driver_id):
        raise DriverOnActiveRideError


def _ensure_can_go_online(profile: DriverProfile | None) -> None:
    if profile is None or profile.approval_status is not ApprovalStatus.APPROVED:
        raise DriverNotApprovedError
    if missing := missing_fields(profile):
        raise DriverProfileIncompleteError(missing)


def _check_vehicle_year(year: int, *, newest: int) -> None:
    if not VEHICLE_MIN_YEAR <= year <= newest:
        raise VehicleYearOutOfRangeError(VEHICLE_MIN_YEAR, newest)


def _apply_vehicle(profile: DriverProfile, data: VehicleInput, now: datetime) -> bool:
    values = {name: getattr(data, name) for name in _VEHICLE_FIELDS}
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


async def list_drivers(
    db: AsyncSession, status: ApprovalStatus | None, *, limit: int, offset: int
) -> DriverPage:
    async with read_transaction(db):
        rows = await _driver_rows(db, status, limit=limit, offset=offset)
        total = await _count_drivers(db, status)
    return DriverPage(rows=rows, total=total)


async def approve_driver(
    db: AsyncSession,
    driver_id: uuid.UUID,
    admin_id: uuid.UUID,
    *,
    car_class: Tariff | None = None,
    clock: Clock,
) -> tuple[User, DriverProfile]:
    """Approving an approved driver again keeps the first approval; ``car_class`` still applies."""
    async with db.begin():
        user = await _get_driver_user(db, driver_id)
        if user is None:
            raise DriverNotFoundError
        profile = await _get_profile_for_update(db, driver_id)
        missing = missing_fields(profile)
        if profile is None or missing:
            raise DriverProfileIncompleteError(missing)
        now = clock.now()
        if profile.approval_status is not ApprovalStatus.APPROVED:
            profile.approval_status = ApprovalStatus.APPROVED
            profile.approved_at = now
            profile.approved_by = admin_id
            profile.updated_at = now
        if car_class is not None:
            await _apply_car_class(db, profile, car_class, now)
    return user, profile


async def set_car_class(
    db: AsyncSession, driver_id: uuid.UUID, car_class: Tariff, *, clock: Clock
) -> tuple[User, DriverProfile]:
    """Admin only; a lowered class revokes pending offers of the tariffs it no longer serves."""
    async with db.begin():
        user = await _get_driver_user(db, driver_id)
        if user is None:
            raise DriverNotFoundError
        profile = await _get_profile_for_update(db, driver_id)
        if profile is None or profile.vehicle is None:
            raise DriverProfileIncompleteError(["vehicle"])
        await _apply_car_class(db, profile, car_class, clock.now())
    return user, profile


async def _apply_car_class(
    db: AsyncSession, profile: DriverProfile, car_class: Tariff, now: datetime
) -> None:
    vehicle = profile.vehicle
    if vehicle is None or vehicle.car_class is car_class:
        return
    vehicle.car_class = car_class
    vehicle.updated_at = now
    await revoke_driver_offers(db, profile.user_id, now, tariffs=tariffs_above(car_class))


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


async def _driver_rows(
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
