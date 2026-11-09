import uuid

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import ScalarSelect

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.admin.exceptions import (
    AccountHasActiveRideError,
    AdminAccountProtectedError,
    UserNotFoundError,
)
from taxi_service.modules.admin.schemas import AccountAccessUpdate, AdminOverview
from taxi_service.modules.auth.models import AuthSession
from taxi_service.modules.drivers.models import ApprovalStatus, DriverProfile
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.dispatch import revoke_driver_offers
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import ACTIVE_RIDE_STATUSES, RideStatus
from taxi_service.modules.users.models import User, UserProfile, UserRole
from taxi_service.modules.users.service import UserListRow


async def read_user(db: AsyncSession, user_id: uuid.UUID) -> UserListRow:
    async with read_transaction(db):
        row = await db.execute(
            select(
                User.id,
                User.username,
                User.role,
                User.created_at,
                UserProfile.display_name,
                User.blocked_at,
                User.block_reason,
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id == user_id)
        )
        found = row.one_or_none()
        if found is None:
            raise UserNotFoundError
        return UserListRow(*found)


async def set_account_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    admin_id: uuid.UUID,
    data: AccountAccessUpdate,
    *,
    clock: Clock,
) -> None:
    async with db.begin():
        # Same order as ride commands before changing a driver's availability.
        rides = (
            await db.scalars(
                select(Ride)
                .where(
                    or_(Ride.passenger_id == user_id, Ride.driver_id == user_id),
                    Ride.status.in_(ACTIVE_RIDE_STATUSES),
                )
                .with_for_update()
            )
        ).all()
        user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise UserNotFoundError
        if user.role is UserRole.ADMIN:
            raise AdminAccountProtectedError
        if data.blocked:
            if any(ride.status in ACTIVE_RIDE_STATUSES for ride in rides):
                raise AccountHasActiveRideError
            unpaid_cash = await db.scalar(
                select(Payment.id)
                .join(Ride, Ride.id == Payment.ride_id)
                .where(
                    Ride.driver_id == user_id,
                    Ride.status == RideStatus.COMPLETED,
                    Payment.method == PaymentMethod.CASH,
                    Payment.status == PaymentStatus.UNPAID,
                )
                .limit(1)
            )
            if unpaid_cash is not None:
                raise AccountHasActiveRideError
            if user.blocked_at is not None:
                return
            now = clock.now()
            user.blocked_at, user.block_reason, user.blocked_by = now, data.reason, admin_id
            await db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await revoke_driver_offers(db, user_id, now)
            await db.execute(
                update(DriverProfile)
                .where(DriverProfile.user_id == user_id)
                .values(is_online=False, updated_at=now)
            )
        else:
            user.blocked_at = user.block_reason = user.blocked_by = None


async def overview(db: AsyncSession) -> AdminOverview:
    def users(*conditions: ColumnElement[bool]) -> ScalarSelect[int]:
        return select(func.count()).select_from(User).where(*conditions).scalar_subquery()

    def rides(*statuses: RideStatus) -> ScalarSelect[int]:
        return (
            select(func.count())
            .select_from(Ride)
            .where(Ride.status.in_(statuses))
            .scalar_subquery()
        )

    pending = (
        select(func.count())
        .select_from(User)
        .outerjoin(DriverProfile, DriverProfile.user_id == User.id)
        .where(
            User.role == UserRole.DRIVER,
            User.blocked_at.is_(None),
            or_(
                DriverProfile.user_id.is_(None),
                DriverProfile.approval_status == ApprovalStatus.PENDING,
            ),
        )
        .scalar_subquery()
    )
    online = (
        select(func.count())
        .select_from(DriverProfile)
        .join(User, User.id == DriverProfile.user_id)
        .where(DriverProfile.is_online.is_(True), User.blocked_at.is_(None))
        .scalar_subquery()
    )
    collected = (
        select(func.coalesce(func.sum(Payment.amount_kzt), 0))
        .where(
            Payment.status == PaymentStatus.PAID,
            Payment.ride_id.in_(select(Ride.id).where(Ride.status == RideStatus.COMPLETED)),
        )
        .scalar_subquery()
    )
    outstanding = (
        select(func.coalesce(func.sum(Payment.amount_kzt), 0))
        .where(
            Payment.status == PaymentStatus.UNPAID,
            Payment.method == PaymentMethod.CASH,
            Payment.ride_id.in_(select(Ride.id).where(Ride.status == RideStatus.COMPLETED)),
        )
        .scalar_subquery()
    )
    statement = select(
        users().label("total_users"),
        users(User.blocked_at.is_not(None)).label("blocked_users"),
        pending.label("pending_drivers"),
        online.label("online_drivers"),
        rides(*ACTIVE_RIDE_STATUSES).label("active_rides"),
        rides(RideStatus.COMPLETED).label("completed_rides"),
        rides(RideStatus.CANCELLED, RideStatus.NO_DRIVER).label("cancelled_rides"),
        collected.label("collected_kzt"),
        outstanding.label("outstanding_cash_kzt"),
    )
    async with read_transaction(db):
        result = (await db.execute(statement)).one()
    return AdminOverview.model_validate(dict(result._mapping))
