"""Data access for offers and the ride rows dispatch changes; the caller owns the transaction.

Status changes are conditional UPDATEs (``... WHERE status = 'pending'``) that
report whether a row changed, so a stale decision changes nothing. Rows are
locked in the order rides -> ride_offers (``FOR UPDATE``; SQLite has no row
locks and serializes writers with ``BEGIN IMMEDIATE`` instead).
"""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Select, func, select, union, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Update

from taxi_service.database.errors import violates_unique
from taxi_service.modules.rides.models import (
    PENDING_OFFER_DRIVER_INDEX,
    PENDING_OFFER_RIDE_INDEX,
    SEARCH_OFFER_CONSTRAINT,
    Ride,
    RideOffer,
)
from taxi_service.modules.rides.states import OfferStatus, RideStatus


class OfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_ride(self, ride_id: uuid.UUID) -> Ride | None:
        """The ride, fresh from the database and locked for the rest of the transaction."""
        result = await self._session.execute(
            select(Ride)
            .where(Ride.id == ride_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_offer(self, offer_id: uuid.UUID, *, lock: bool = False) -> RideOffer | None:
        """The offer, fresh from the database; ``lock`` only after its ride is locked."""
        query = select(RideOffer).where(RideOffer.id == offer_id)
        if lock:
            query = query.with_for_update()
        result = await self._session.execute(query.execution_options(populate_existing=True))
        return result.scalar_one_or_none()

    async def pending_offer(self, ride_id: uuid.UUID) -> RideOffer | None:
        return await self._session.scalar(
            select(RideOffer).where(
                RideOffer.ride_id == ride_id, RideOffer.status == OfferStatus.PENDING
            )
        )

    async def get_ride(self, ride_id: uuid.UUID) -> Ride | None:
        """The ride as committed, replacing whatever the session still holds."""
        result = await self._session.execute(
            select(Ride).where(Ride.id == ride_id).execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def try_add_offer(self, offer: RideOffer) -> bool:
        """Insert in a savepoint; ``False`` if an offer unique index refused it (a lost race).

        Any other integrity error (a missing driver, a CHECK) is re-raised.
        """
        try:
            async with self._session.begin_nested():
                self._session.add(offer)
                await self._session.flush()
        except IntegrityError as error:
            if not _lost_offer_race(error):
                raise
            return False
        return True

    async def decide_offer(
        self,
        offer_id: uuid.UUID,
        status: OfferStatus,
        now: datetime,
        *,
        unexpired: bool = False,
    ) -> bool:
        """Pending offer -> ``status``; with ``unexpired`` only while ``now < expires_at``."""
        conditions = [RideOffer.id == offer_id]
        if unexpired:
            conditions.append(RideOffer.expires_at > now)
        return await self._decide(conditions, status, now) == 1

    async def expire_overdue(self, ride_id: uuid.UUID, status: OfferStatus, now: datetime) -> int:
        """Pending offers of the ride with ``expires_at <= now`` -> ``status`` (expired)."""
        return await self._decide(
            [RideOffer.ride_id == ride_id, RideOffer.expires_at <= now], status, now
        )

    async def decide_pending_of_ride(
        self, ride_id: uuid.UUID, status: OfferStatus, now: datetime
    ) -> int:
        return await self._decide([RideOffer.ride_id == ride_id], status, now)

    async def decide_pending_of_driver(
        self, driver_id: uuid.UUID, status: OfferStatus, now: datetime
    ) -> int:
        return await self._decide([RideOffer.driver_id == driver_id], status, now)

    async def rides_needing_work(self, now: datetime) -> list[uuid.UUID]:
        """Rides with an overdue pending offer, searching rides without a pending offer,
        and rides that left ``searching`` but still have a pending offer."""
        overdue = select(RideOffer.ride_id).where(
            RideOffer.status == OfferStatus.PENDING, RideOffer.expires_at <= now
        )
        waiting = select(Ride.id).where(
            Ride.status == RideStatus.SEARCHING,
            ~select(RideOffer.id)
            .where(RideOffer.ride_id == Ride.id, RideOffer.status == OfferStatus.PENDING)
            .exists(),
        )
        stray = (
            select(RideOffer.ride_id)
            .join(Ride, Ride.id == RideOffer.ride_id)
            .where(RideOffer.status == OfferStatus.PENDING, Ride.status != RideStatus.SEARCHING)
        )
        rows = await self._session.execute(union(overdue, waiting, stray))
        return sorted(ride_id for (ride_id,) in rows)

    async def pending_for_driver(
        self, driver_id: uuid.UUID, now: datetime, *, limit: int, offset: int
    ) -> list[tuple[RideOffer, Ride]]:
        rows = await self._session.execute(
            _open_offers(driver_id, now)
            .order_by(RideOffer.created_at.desc(), RideOffer.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(offer, ride) for offer, ride in rows]

    async def count_pending_for_driver(self, driver_id: uuid.UUID, now: datetime) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(_open_offers(driver_id, now).subquery())
        )
        return total or 0

    async def _decide(self, conditions: list[Any], status: OfferStatus, now: datetime) -> int:
        statement = (
            update(RideOffer)
            .where(RideOffer.status == OfferStatus.PENDING, *conditions)
            .values(status=status, responded_at=now)
        )
        return await self._rowcount(statement)

    async def _rowcount(self, statement: Update) -> int:
        result = await self._session.execute(
            statement, execution_options={"synchronize_session": False}
        )
        return cast(CursorResult[Any], result).rowcount


def _lost_offer_race(error: IntegrityError) -> bool:
    """One pending offer per ride or per driver, or this driver already asked in this search."""
    return any(
        violates_unique(error, constraint=constraint, table="ride_offers", column=column)
        for constraint, column in (
            (PENDING_OFFER_RIDE_INDEX, "ride_id"),
            (PENDING_OFFER_DRIVER_INDEX, "driver_id"),
            (SEARCH_OFFER_CONSTRAINT, "ride_id"),
        )
    )


def _open_offers(driver_id: uuid.UUID, now: datetime) -> Select[RideOffer, Ride]:
    """Pending offers of the driver that can still be accepted, with their rides."""
    return (
        select(RideOffer, Ride)
        .join(Ride, Ride.id == RideOffer.ride_id)
        .where(
            RideOffer.driver_id == driver_id,
            RideOffer.status == OfferStatus.PENDING,
            RideOffer.expires_at > now,
        )
    )
