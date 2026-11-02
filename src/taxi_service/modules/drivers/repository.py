import uuid

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.drivers.models import ApprovalStatus, DriverProfile, Vehicle
from taxi_service.modules.users.models import User, UserRole


class DriverRepository:
    """Data access for ``driver_profiles`` and ``vehicles``; the caller owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> DriverProfile | None:
        """The profile with its vehicle (joined), or ``None`` before the first write."""
        return await self._session.get(DriverProfile, user_id)

    async def get_for_update(self, user_id: uuid.UUID) -> DriverProfile | None:
        """Like :meth:`get`, locking the profile row for the rest of the write transaction.

        ``FOR NO KEY UPDATE OF driver_profiles``: PostgreSQL refuses to lock the
        nullable side of the vehicle outer join, and the key is never changed,
        so foreign-key checks of rides and ride_offers (``FOR KEY SHARE``) do not
        wait for this lock: a driver going offline cannot deadlock with an
        accept that holds the ride and offer rows (ADR 0006). SQLite has no row
        locks and omits the clause; its writes are serialized by ``BEGIN IMMEDIATE``.
        """
        result = await self._session.execute(
            select(DriverProfile)
            .where(DriverProfile.user_id == user_id)
            .with_for_update(of=DriverProfile, key_share=True)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def add(self, profile: DriverProfile) -> None:
        self._session.add(profile)
        await self._session.flush()

    async def plate_number_taken(self, plate_number: str, *, by_other_than: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(Vehicle.id).where(
                Vehicle.plate_number == plate_number, Vehicle.driver_id != by_other_than
            )
        )
        return found is not None

    async def get_driver_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.scalar(
            select(User).where(User.id == user_id, User.role == UserRole.DRIVER)
        )

    async def list_drivers(
        self, status: ApprovalStatus | None, *, limit: int, offset: int
    ) -> list[tuple[User, DriverProfile | None]]:
        """Driver accounts, newest registration first (then id DESC), with their profiles."""
        rows = await self._session.execute(
            _drivers(status)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(user, profile) for user, profile in rows]

    async def count_drivers(self, status: ApprovalStatus | None) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(_drivers(status).subquery())
        )
        return total or 0


def _drivers(status: ApprovalStatus | None) -> Select[User, DriverProfile]:
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
