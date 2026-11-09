"""Ride lists: two statements a page, rows without ``route_geometry``."""

import dataclasses
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, raiseload

from taxi_service.database.search import matches_text
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.exceptions import ForbiddenError
from taxi_service.modules.drivers.models import DriverProfile, Vehicle
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.users.models import User, UserProfile, UserRole


@dataclass(frozen=True, slots=True, kw_only=True)
class RideFilters:
    """AND of the set fields; ``[created_from, created_to)``; empty ``statuses`` is any."""

    statuses: frozenset[RideStatus] = frozenset()
    created_from: datetime | None = None
    created_to: datetime | None = None
    passenger_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    query: str = ""
    payment_status: PaymentStatus | None = None
    payment_method: PaymentMethod | None = None
    tariff: Tariff | None = None


@dataclass(frozen=True, slots=True)
class RideRow:
    ride: Ride
    payment_status: PaymentStatus | None
    payment_method: PaymentMethod | None
    passenger_name: str | None = None
    driver_name: str | None = None


@dataclass(frozen=True, slots=True)
class RidePage:
    rows: Sequence[RideRow]
    total: int


async def list_history(
    db: AsyncSession,
    viewer_id: uuid.UUID,
    viewer_role: UserRole,
    filters: RideFilters,
    *,
    limit: int,
    offset: int,
) -> RidePage:
    """A passenger's own rides or a driver's assigned ones; admins use ``list_rides``."""
    if viewer_role is UserRole.PASSENGER:
        scoped = dataclasses.replace(filters, passenger_id=viewer_id)
    elif viewer_role is UserRole.DRIVER:
        scoped = dataclasses.replace(filters, driver_id=viewer_id)
    else:
        raise ForbiddenError
    return await list_rides(db, scoped, limit=limit, offset=offset)


async def list_all_rides(
    db: AsyncSession,
    filters: RideFilters,
    *,
    passenger_id: uuid.UUID | None,
    driver_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> RidePage:
    scoped = dataclasses.replace(filters, passenger_id=passenger_id, driver_id=driver_id)
    return await list_rides(db, scoped, limit=limit, offset=offset, include_people=True)


async def list_rides(
    db: AsyncSession, filters: RideFilters, *, limit: int, offset: int, include_people: bool = False
) -> RidePage:
    """Newest first (``created_at DESC, id DESC``)."""
    conditions = _conditions(filters)
    async with read_transaction(db):
        result = await db.execute(
            _page(conditions, limit=limit, offset=offset, include_people=include_people)
        )
        rows = [RideRow(*row) for row in result]
        total = await db.scalar(select(func.count()).select_from(Ride).where(*conditions))
        return RidePage(rows=rows, total=total or 0)


def _page(
    conditions: list[ColumnElement[bool]], *, limit: int, offset: int, include_people: bool = False
) -> Select[Ride, PaymentStatus, PaymentMethod]:
    query = (
        select(Ride, Payment.status, Payment.method)
        .outerjoin(Payment, Payment.ride_id == Ride.id)
        .options(defer(Ride.route_geometry, raiseload=True), raiseload(Ride.payment))
        .where(*conditions)
        .order_by(Ride.created_at.desc(), Ride.id.desc())
        .limit(limit)
        .offset(offset)
    )

    if include_people:
        passenger = (
            select(func.coalesce(UserProfile.display_name, User.username))
            .select_from(User)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.id == Ride.passenger_id)
            .correlate(Ride)
            .scalar_subquery()
        )
        driver = (
            select(func.coalesce(DriverProfile.full_name, User.username))
            .select_from(User)
            .outerjoin(DriverProfile, DriverProfile.user_id == User.id)
            .where(User.id == Ride.driver_id)
            .correlate(Ride)
            .scalar_subquery()
        )
        query = query.add_columns(passenger, driver)
    return query


def _conditions(filters: RideFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.passenger_id is not None:
        conditions.append(Ride.passenger_id == filters.passenger_id)
    if filters.driver_id is not None:
        conditions.append(Ride.driver_id == filters.driver_id)
    if filters.statuses:
        conditions.append(Ride.status.in_(sorted(filters.statuses)))
    if filters.created_from is not None:
        conditions.append(Ride.created_at >= filters.created_from)
    if filters.created_to is not None:
        conditions.append(Ride.created_at < filters.created_to)
    if filters.query.strip():
        people = (
            select(User.id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(DriverProfile, DriverProfile.user_id == User.id)
            .outerjoin(Vehicle, Vehicle.driver_id == User.id)
            .where(
                matches_text(
                    filters.query,
                    User.username,
                    UserProfile.display_name,
                    DriverProfile.full_name,
                    DriverProfile.phone,
                    Vehicle.plate_number,
                )
            )
        )
        terms: list[ColumnElement[bool]] = [
            Ride.passenger_id.in_(people),
            Ride.driver_id.in_(people),
        ]
        with suppress(ValueError):
            terms.append(Ride.id == uuid.UUID(filters.query.strip()))
        conditions.append(or_(*terms))
    if filters.payment_status is not None or filters.payment_method is not None:
        payments = select(Payment.ride_id)
        if filters.payment_status is not None:
            payments = payments.where(Payment.status == filters.payment_status)
        if filters.payment_method is not None:
            payments = payments.where(Payment.method == filters.payment_method)
        conditions.append(Ride.id.in_(payments))
    if filters.tariff is not None:
        conditions.append(Ride.tariff == filters.tariff)
    return conditions
