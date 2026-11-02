"""Read side of rides: a participant's history and the admin list (MVP_SPEC §3, §8).

One page costs two statements whatever its size: the rows and the total.
Rows are loaded without ``route_geometry``; the full route is read with
``GET /rides/{id}``.
"""

import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.exceptions import ForbiddenError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole


@dataclass(frozen=True, slots=True, kw_only=True)
class RideFilters:
    """Conditions combined with AND; empty ``statuses`` means any status.

    ``created_from`` is inclusive and ``created_to`` exclusive: ``[from, to)``.
    """

    statuses: frozenset[RideStatus] = frozenset()
    created_from: datetime | None = None
    created_to: datetime | None = None
    passenger_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class RidePage:
    rides: Sequence[Ride]
    total: int


class RideQueries:
    """Read-only ride lists, newest first (``created_at DESC, id DESC``)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def history(
        self,
        viewer_id: uuid.UUID,
        viewer_role: UserRole,
        filters: RideFilters,
        *,
        limit: int,
        offset: int,
    ) -> RidePage:
        """A passenger's own rides, or the rides a driver is assigned to now.

        Admins have no history of their own (403); they use :meth:`list_rides`.
        """
        if viewer_role is UserRole.PASSENGER:
            scoped = dataclasses.replace(filters, passenger_id=viewer_id)
        elif viewer_role is UserRole.DRIVER:
            scoped = dataclasses.replace(filters, driver_id=viewer_id)
        else:
            raise ForbiddenError
        return await self.list_rides(scoped, limit=limit, offset=offset)

    async def list_rides(self, filters: RideFilters, *, limit: int, offset: int) -> RidePage:
        conditions = _conditions(filters)
        async with read_transaction(self._session):
            rides = await self._session.scalars(_page(conditions, limit=limit, offset=offset))
            total = await self._session.scalar(
                select(func.count()).select_from(Ride).where(*conditions)
            )
            return RidePage(rides=rides.all(), total=total or 0)


def _page(conditions: list[ColumnElement[bool]], *, limit: int, offset: int) -> Select[Ride]:
    return (
        select(Ride)
        .options(defer(Ride.route_geometry, raiseload=True))
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
