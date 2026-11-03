"""Driver search, one offer at a time; all search state is in the database (ADR 0006)."""

import logging
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, Select, func, select, union, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.errors import violates_unique
from taxi_service.database.session import read_transaction
from taxi_service.modules.drivers.candidates import SearchScope, find_nearby_candidates
from taxi_service.modules.payments import records as payment_records
from taxi_service.modules.ratings import records as rating_records
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.rides.exceptions import (
    DriverBusyError,
    InvalidOfferTransitionError,
    InvalidRideTransitionError,
    OfferExpiredError,
    OfferNotFoundError,
)
from taxi_service.modules.rides.models import (
    ACTIVE_DRIVER_RIDE_INDEX,
    PENDING_OFFER_DRIVER_INDEX,
    PENDING_OFFER_RIDE_INDEX,
    SEARCH_OFFER_CONSTRAINT,
    Ride,
    RideOffer,
)
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.schemas import pickup_of
from taxi_service.modules.rides.states import (
    SYSTEM_ACTOR,
    OfferCommand,
    OfferStatus,
    RideCommand,
    RideStatus,
    can_accept_offer,
    is_offer_command_already_applied,
    is_offer_expired,
    next_offer_status,
    next_status,
)
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.rides.transitions import lock_ride, move_ride

logger = logging.getLogger(__name__)

SEARCH_START_STEP = timedelta(microseconds=1)

# Candidates tried in one step when a nearer one was reserved by a concurrent search.
CANDIDATE_BATCH = 3

_EXPIRED = next_offer_status(OfferStatus.PENDING, OfferCommand.EXPIRE)
_REVOKED = next_offer_status(OfferStatus.PENDING, OfferCommand.REVOKE)


@dataclass(frozen=True, slots=True)
class OfferPage:
    rows: list[tuple[RideOffer, Ride]]
    total: int
    passenger_ratings: Mapping[uuid.UUID, RatingSummary]


async def process_ride(
    db: AsyncSession,
    ride_id: uuid.UUID,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> Ride | None:
    """One idempotent search step; call it after the ride's own transaction committed."""
    async with db.begin():
        ride = await lock_ride(db, ride_id)
        if ride is not None:
            await _step(db, ride, clock.now(), policy)
    return ride


async def start_search(
    db: AsyncSession,
    ride_id: uuid.UUID,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> Ride:
    """Takes the id: a rolled-back step expires every object of the session."""
    processed: Ride | None
    try:
        processed = await process_ride(db, ride_id, clock=clock, policy=policy)
    except Exception:
        logger.exception("Dispatch step after commit failed for ride %s", ride_id)
        processed = None
    if processed is None:
        async with read_transaction(db):
            processed = await _fresh_ride(db, ride_id)
    if processed is None:
        raise RuntimeError(f"Ride {ride_id} disappeared after it was created")
    return processed


async def process_due(
    db: AsyncSession,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    failing_rides: set[uuid.UUID] | None = None,
) -> int:
    """Loop pass: how many rides needed a step; ``failing_rides`` keeps one traceback per series."""
    failing = failing_rides if failing_rides is not None else set()
    async with read_transaction(db):
        ride_ids = await _rides_needing_work(db, clock.now())
    failing.intersection_update(ride_ids)
    for ride_id in ride_ids:
        try:
            await process_ride(db, ride_id, clock=clock, policy=policy)
        except Exception as error:
            if ride_id in failing:
                logger.warning("Dispatch step failed again for ride %s: %r", ride_id, error)
            else:
                logger.exception("Dispatch step failed for ride %s", ride_id)
                failing.add(ride_id)
        else:
            failing.discard(ride_id)
    return len(ride_ids)


async def accept_offer(
    db: AsyncSession,
    offer_id: uuid.UUID,
    driver_id: uuid.UUID,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> Ride:
    """An overdue offer is marked expired and the next candidate asked before the 409."""
    try:
        async with db.begin():
            outcome = await _accept(db, offer_id, driver_id, clock, policy)
    except IntegrityError as error:
        if violates_unique(
            error, constraint=ACTIVE_DRIVER_RIDE_INDEX, table="rides", column="driver_id"
        ):
            raise DriverBusyError from error
        raise
    if isinstance(outcome, OfferExpiredError):
        raise outcome
    return outcome


async def reject_offer(
    db: AsyncSession,
    offer_id: uuid.UUID,
    driver_id: uuid.UUID,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> tuple[RideOffer, Ride]:
    """The next candidate is asked in the same transaction."""
    async with db.begin():
        offer, ride = await _addressed(db, offer_id, driver_id)
        now = clock.now()
        if is_offer_command_already_applied(offer.status, OfferCommand.REJECT):
            return offer, ride
        expired = await _expired(db, offer, ride, now, policy)
        if expired is None:
            target = next_offer_status(offer.status, OfferCommand.REJECT)
            await _decide_offer(db, offer.id, target, now)
            await _step(db, ride, now, policy)
            await db.refresh(offer)
    if expired is not None:
        raise expired
    return offer, ride


async def list_pending_offers(
    db: AsyncSession, driver_id: uuid.UUID, *, clock: Clock, limit: int, offset: int
) -> OfferPage:
    """Offers that can still be accepted, newest first."""
    now = clock.now()
    open_offers = _open_offers(driver_id, now)
    async with read_transaction(db):
        rows = await db.execute(
            open_offers.order_by(RideOffer.created_at.desc(), RideOffer.id.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await db.scalar(select(func.count()).select_from(open_offers.subquery()))
        page = [(offer, ride) for offer, ride in rows]
        ratings = await rating_records.summaries(db, [ride.passenger_id for _, ride in page])
        return OfferPage(rows=page, total=total or 0, passenger_ratings=ratings)


async def revoke_pending_offers(db: AsyncSession, ride_id: uuid.UUID, now: datetime) -> int:
    """In the caller's transaction, after it locked the ride (cancel)."""
    return await _decide(db, [RideOffer.ride_id == ride_id], _REVOKED, now)


async def revoke_driver_offers(
    db: AsyncSession,
    driver_id: uuid.UUID,
    now: datetime,
    *,
    tariffs: Collection[Tariff] | None = None,
) -> int:
    """In the caller's transaction; the ride stays searching and the loop asks the next driver.

    ``tariffs`` limits it to offers of rides in these tariffs (a lowered car class).
    """
    conditions = [RideOffer.driver_id == driver_id]
    if tariffs is not None:
        conditions.append(RideOffer.ride_id.in_(select(Ride.id).where(Ride.tariff.in_(tariffs))))
    return await _decide(db, conditions, _REVOKED, now)


def restart_search(ride: Ride, now: datetime, policy: DispatchPolicy) -> None:
    """New window strictly after the previous one, so their offers never share a start."""
    started_at = max(now, ride.search_started_at + SEARCH_START_STEP)
    ride.search_started_at = started_at
    ride.search_deadline = started_at + policy.search_budget


async def _accept(
    db: AsyncSession,
    offer_id: uuid.UUID,
    driver_id: uuid.UUID,
    clock: Clock,
    policy: DispatchPolicy,
) -> Ride | OfferExpiredError:
    offer, ride = await _addressed(db, offer_id, driver_id)
    now = clock.now()
    if ride.status is RideStatus.CANCELLED:
        raise InvalidRideTransitionError(
            current_status=ride.status.value, command=RideCommand.ASSIGN.value
        )
    if is_offer_command_already_applied(offer.status, OfferCommand.ACCEPT):
        if ride.driver_id == driver_id:
            return ride
        # Accepted earlier, then released: the assignment is gone.
        raise InvalidOfferTransitionError(
            current_status=offer.status.value, command=OfferCommand.ACCEPT.value
        )
    expired = await _expired(db, offer, ride, now, policy)
    if expired is not None:
        return expired
    target = next_offer_status(offer.status, OfferCommand.ACCEPT)  # 409 unless pending
    assigned = next_status(ride.status, RideCommand.ASSIGN, SYSTEM_ACTOR)
    # The conditional UPDATEs repeat the checks in SQL: a miss must never assign the ride.
    decided = can_accept_offer(
        offer.status, now=now, expires_at=offer.expires_at
    ) and await _decide_offer(db, offer.id, target, now, unexpired=True)
    if not decided or not await move_ride(
        db,
        ride,
        command=RideCommand.ASSIGN,
        to_status=assigned,
        now=now,
        actor_id=driver_id,
        values={"driver_id": driver_id, "assigned_at": now},
    ):
        raise InvalidOfferTransitionError(
            current_status=offer.status.value, command=OfferCommand.ACCEPT.value
        )
    # Locks the payment last (rides -> ride_offers -> payments).
    await payment_records.charge_kaspi(db, ride, now)
    return ride


async def _addressed(
    db: AsyncSession, offer_id: uuid.UUID, driver_id: uuid.UUID
) -> tuple[RideOffer, Ride]:
    """The offer and its ride, locked ride first; 404 unless addressed to ``driver_id``."""
    offer = await _get_offer(db, offer_id)
    if offer is None or offer.driver_id != driver_id:
        raise OfferNotFoundError
    ride = await lock_ride(db, offer.ride_id)
    locked = await _get_offer(db, offer_id, lock=True)
    if ride is None or locked is None:
        raise OfferNotFoundError
    return locked, ride


async def _expired(
    db: AsyncSession, offer: RideOffer, ride: Ride, now: datetime, policy: DispatchPolicy
) -> OfferExpiredError | None:
    """The error to raise after commit; an overdue offer is marked and the search moves on."""
    if offer.status is OfferStatus.EXPIRED:
        return OfferExpiredError()
    if offer.status is OfferStatus.PENDING and is_offer_expired(
        now=now, expires_at=offer.expires_at
    ):
        await _step(db, ride, now, policy)
        return OfferExpiredError()
    return None


async def _step(db: AsyncSession, ride: Ride, now: datetime, policy: DispatchPolicy) -> None:
    """One search step on a ride already locked by this transaction."""
    await _decide(db, [RideOffer.ride_id == ride.id, RideOffer.expires_at <= now], _EXPIRED, now)
    if ride.status is not RideStatus.SEARCHING:
        await _decide(db, [RideOffer.ride_id == ride.id], _REVOKED, now)
        return
    if await _pending_offer(db, ride.id) is not None:
        return
    if now < ride.search_deadline and await _offer_to_nearest(db, ride, now, policy):
        return
    no_driver = next_status(ride.status, RideCommand.MARK_NO_DRIVER, SYSTEM_ACTOR)
    if await move_ride(
        db,
        ride,
        command=RideCommand.MARK_NO_DRIVER,
        to_status=no_driver,
        now=now,
        actor_id=None,
    ):
        await payment_records.refund_if_paid(db, ride, now)


async def _offer_to_nearest(
    db: AsyncSession, ride: Ride, now: datetime, policy: DispatchPolicy
) -> bool:
    """``False`` only without candidates; if all were taken meanwhile the next pass retries."""
    candidates = await find_nearby_candidates(
        db,
        pickup_of(ride),
        now=now,
        radius_m=policy.radius_m,
        max_location_age_s=policy.max_location_age_s,
        in_search=SearchScope(ride.id, ride.search_started_at),
        tariff=ride.tariff,
        limit=CANDIDATE_BATCH,
    )
    if not candidates:
        return False
    for candidate in candidates:
        offer = RideOffer(
            id=uuid.uuid4(),
            ride_id=ride.id,
            driver_id=candidate.driver_id,
            status=OfferStatus.PENDING,
            created_at=now,
            expires_at=now + policy.offer_ttl,
            responded_at=None,
            search_started_at=ride.search_started_at,
        )
        if await _try_add_offer(db, offer):
            return True
    return True


async def _get_offer(
    db: AsyncSession, offer_id: uuid.UUID, *, lock: bool = False
) -> RideOffer | None:
    """Fresh from the database; ``lock`` only after its ride is locked."""
    query = select(RideOffer).where(RideOffer.id == offer_id)
    if lock:
        query = query.with_for_update()
    result = await db.execute(query.execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def _pending_offer(db: AsyncSession, ride_id: uuid.UUID) -> RideOffer | None:
    return await db.scalar(
        select(RideOffer).where(
            RideOffer.ride_id == ride_id, RideOffer.status == OfferStatus.PENDING
        )
    )


async def _fresh_ride(db: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    result = await db.execute(
        select(Ride).where(Ride.id == ride_id).execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _try_add_offer(db: AsyncSession, offer: RideOffer) -> bool:
    """``False`` if an offer unique index refused it (a lost race); other errors propagate."""
    try:
        async with db.begin_nested():
            db.add(offer)
            await db.flush()
    except IntegrityError as error:
        if not _lost_offer_race(error):
            raise
        return False
    return True


async def _decide_offer(
    db: AsyncSession,
    offer_id: uuid.UUID,
    status: OfferStatus,
    now: datetime,
    *,
    unexpired: bool = False,
) -> bool:
    conditions = [RideOffer.id == offer_id]
    if unexpired:
        conditions.append(RideOffer.expires_at > now)
    return await _decide(db, conditions, status, now) == 1


async def _decide(
    db: AsyncSession,
    conditions: list[ColumnElement[bool]],
    status: OfferStatus,
    now: datetime,
) -> int:
    """Conditional UPDATE of pending offers; a stale decision changes nothing."""
    statement = (
        update(RideOffer)
        .where(RideOffer.status == OfferStatus.PENDING, *conditions)
        .values(status=status, responded_at=now)
    )
    result = await db.execute(statement, execution_options={"synchronize_session": False})
    return cast(CursorResult[Any], result).rowcount


async def _rides_needing_work(db: AsyncSession, now: datetime) -> list[uuid.UUID]:
    """Overdue pending offers, searching rides without one, and stray offers of left rides."""
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
    rows = await db.execute(union(overdue, waiting, stray))
    return sorted(ride_id for (ride_id,) in rows)


def _lost_offer_race(error: IntegrityError) -> bool:
    return any(
        violates_unique(error, constraint=constraint, table="ride_offers", column=column)
        for constraint, column in (
            (PENDING_OFFER_RIDE_INDEX, "ride_id"),
            (PENDING_OFFER_DRIVER_INDEX, "driver_id"),
            (SEARCH_OFFER_CONSTRAINT, "ride_id"),
        )
    )


def _open_offers(driver_id: uuid.UUID, now: datetime) -> Select[RideOffer, Ride]:
    return (
        select(RideOffer, Ride)
        .join(Ride, Ride.id == RideOffer.ride_id)
        .where(
            RideOffer.driver_id == driver_id,
            RideOffer.status == OfferStatus.PENDING,
            RideOffer.expires_at > now,
        )
    )
