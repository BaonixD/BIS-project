"""Ride lists: two statements a page, rows without ``route_geometry``."""

import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, raiseload

from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.exceptions import ForbiddenError
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole


@dataclass(frozen=True, slots=True, kw_only=True)
class RideFilters:
    """AND of the set fields; ``[created_from, created_to)``; empty ``statuses`` is any."""

    statuses: frozenset[RideStatus] = frozenset()
    created_from: datetime | None = None
    created_to: datetime | None = None
    passenger_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class RideRow:
    ride: Ride
    payment_status: PaymentStatus | None
    payment_method: PaymentMethod | None


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
    return await list_rides(db, scoped, limit=limit, offset=offset)


async def list_rides(
    db: AsyncSession, filters: RideFilters, *, limit: int, offset: int
) -> RidePage:
    """Newest first (``created_at DESC, id DESC``)."""
    conditions = _conditions(filters)
    async with read_transaction(db):
        result = await db.execute(_page(conditions, limit=limit, offset=offset))
        rows = [RideRow(ride, status, method) for ride, status, method in result]
        total = await db.scalar(select(func.count()).select_from(Ride).where(*conditions))
        return RidePage(rows=rows, total=total or 0)


def _page(
    conditions: list[ColumnElement[bool]], *, limit: int, offset: int
) -> Select[Ride, PaymentStatus, PaymentMethod]:
    return (
        select(Ride, Payment.status, Payment.method)
        .outerjoin(Payment, Payment.ride_id == Ride.id)
        .options(defer(Ride.route_geometry, raiseload=True), raiseload(Ride.payment))
        .where(*conditions)
        .order_by(Ride.created_at.desc(), Ride.id.desc())
        .limit(limit)
        .offset(offset)
    )


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
    return conditions
