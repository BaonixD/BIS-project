"""Driver search: one offer at a time to the nearest candidate (MVP_SPEC §6, ADR 0006).

All search state lives in the database (``rides.search_deadline``,
``ride_offers``), so any process can continue a search after a restart. A
search step on one ride runs in one short write transaction:

1. lock the ride; mark its pending offers with ``now >= expires_at`` expired;
2. a ride that is no longer ``searching`` loses any pending offer (revoked);
3. a pending offer still running: nothing to do;
4. ``now >= search_deadline`` or no candidate: ``no_driver``;
5. otherwise the nearest candidate gets a new offer for ``offer_ttl``.

Steps are idempotent; concurrent steps are serialized by the ride lock (SQLite:
``BEGIN IMMEDIATE``) and the unique indexes refuse a second pending offer.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.errors import violates_unique
from taxi_service.database.session import read_transaction
from taxi_service.modules.drivers.candidates import find_nearby_candidates
from taxi_service.modules.rides.exceptions import (
    DriverBusyError,
    InvalidOfferTransitionError,
    OfferExpiredError,
    OfferNotFoundError,
)
from taxi_service.modules.rides.models import ACTIVE_DRIVER_RIDE_INDEX, Ride, RideOffer
from taxi_service.modules.rides.offer_repository import OfferRepository
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

logger = logging.getLogger(__name__)

# Candidates tried in one step when a nearer one was reserved by a concurrent search.
CANDIDATE_BATCH = 3

_EXPIRED = next_offer_status(OfferStatus.PENDING, OfferCommand.EXPIRE)
_REVOKED = next_offer_status(OfferStatus.PENDING, OfferCommand.REVOKE)


@dataclass(frozen=True, slots=True)
class OfferPage:
    rows: list[tuple[RideOffer, Ride]]
    total: int


class DispatchService:
    """Search steps, offer answers and the driver's offer list; each call is one transaction."""

    def __init__(
        self, session: AsyncSession, clock: Clock, policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY
    ) -> None:
        self._session = session
        self._clock = clock
        self._policy = policy
        self._offers = OfferRepository(session)

    async def process_ride(self, ride_id: uuid.UUID) -> Ride | None:
        """One search step for the ride (module docstring); the ride after it, if it exists.

        Call it after the transaction that created the ride or restarted its
        search has committed; repeating it is harmless.
        """
        async with self._session.begin():
            ride = await self._offers.lock_ride(ride_id)
            if ride is not None:
                await self._step(ride, self._clock.now())
        return ride

    async def process_due(self) -> int:
        """Loop pass: a read-only check for rides needing a step, then one step per ride.

        Returns how many rides needed a step. A failing ride is logged and does
        not stop the others.
        """
        async with read_transaction(self._session):
            ride_ids = await self._offers.rides_needing_work(self._clock.now())
        for ride_id in ride_ids:
            try:
                await self.process_ride(ride_id)
            except Exception:
                logger.exception("Dispatch step failed for ride %s", ride_id)
        return len(ride_ids)

    async def accept_offer(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> Ride:
        """Assign the ride to the offer's driver while the offer is pending and in time.

        Accepting an offer this driver already accepted returns the ride again.
        ``now >= expires_at`` is 409 ``offer_expired`` even if the loop has not
        marked it yet; the offer is then marked expired and the next candidate
        asked. Other decided offers: 409 ``invalid_offer_transition``.
        """
        try:
            async with self._session.begin():
                outcome = await self._accept(offer_id, driver_id)
        except IntegrityError as error:
            if violates_unique(
                error, constraint=ACTIVE_DRIVER_RIDE_INDEX, table="rides", column="driver_id"
            ):
                raise DriverBusyError from error
            raise
        if isinstance(outcome, OfferExpiredError):
            raise outcome
        return outcome

    async def reject_offer(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> RideOffer:
        """Decline a pending offer; the next candidate is asked in the same transaction.

        Rejecting again returns the rejected offer; after the deadline it is 409
        ``offer_expired``.
        """
        async with self._session.begin():
            offer, ride = await self._addressed(offer_id, driver_id)
            now = self._clock.now()
            if is_offer_command_already_applied(offer.status, OfferCommand.REJECT):
                return offer
            expired = await self._expired(offer, ride, now)
            if expired is None:
                target = next_offer_status(offer.status, OfferCommand.REJECT)
                await self._offers.decide_offer(offer.id, target, now)
                await self._step(ride, now)
                await self._session.refresh(offer)
        if expired is not None:
            raise expired
        return offer

    async def pending_offers(self, driver_id: uuid.UUID, *, limit: int, offset: int) -> OfferPage:
        """The driver's pending offers that can still be accepted, newest first."""
        now = self._clock.now()
        async with read_transaction(self._session):
            rows = await self._offers.pending_for_driver(driver_id, now, limit=limit, offset=offset)
            total = await self._offers.count_pending_for_driver(driver_id, now)
        return OfferPage(rows=rows, total=total)

    async def _accept(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> Ride | OfferExpiredError:
        offer, ride = await self._addressed(offer_id, driver_id)
        now = self._clock.now()
        if is_offer_command_already_applied(offer.status, OfferCommand.ACCEPT):
            if ride.driver_id == driver_id:
                return ride
            # Accepted earlier, then released: the assignment is gone.
            raise InvalidOfferTransitionError(
                current_status=offer.status.value, command=OfferCommand.ACCEPT.value
            )
        expired = await self._expired(offer, ride, now)
        if expired is not None:
            return expired
        target = next_offer_status(offer.status, OfferCommand.ACCEPT)
        assert can_accept_offer(offer.status, now=now, expires_at=offer.expires_at)
        assigned = next_status(ride.status, RideCommand.ASSIGN, SYSTEM_ACTOR)
        decided = await self._offers.decide_offer(offer.id, target, now, unexpired=True)
        moved = await self._offers.move_ride(
            ride.id, from_status=ride.status, to_status=assigned, now=now, driver_id=driver_id
        )
        if not (decided and moved):  # unreachable while the ride row is locked
            raise InvalidOfferTransitionError(
                current_status=offer.status.value, command=OfferCommand.ACCEPT.value
            )
        await self._session.refresh(ride)
        return ride

    async def _addressed(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> tuple[RideOffer, Ride]:
        """The offer and its ride, locked ride first; 404 unless addressed to ``driver_id``."""
        offer = await self._offers.get_offer(offer_id)
        if offer is None or offer.driver_id != driver_id:
            raise OfferNotFoundError
        ride = await self._offers.lock_ride(offer.ride_id)
        locked = await self._offers.get_offer(offer_id, lock=True)
        if ride is None or locked is None:
            raise OfferNotFoundError
        return locked, ride

    async def _expired(
        self, offer: RideOffer, ride: Ride, now: datetime
    ) -> OfferExpiredError | None:
        """An error to raise after commit if the offer's time is up; marks it and moves on."""
        if offer.status is OfferStatus.EXPIRED:
            return OfferExpiredError()
        if offer.status is OfferStatus.PENDING and is_offer_expired(
            now=now, expires_at=offer.expires_at
        ):
            await self._step(ride, now)
            return OfferExpiredError()
        return None

    async def _step(self, ride: Ride, now: datetime) -> None:
        """One search step on a ride already locked by this transaction."""
        await self._offers.expire_overdue(ride.id, _EXPIRED, now)
        if ride.status is not RideStatus.SEARCHING:
            await self._offers.decide_pending_of_ride(ride.id, _REVOKED, now)
            return
        if await self._offers.pending_offer(ride.id) is not None:
            return
        if now < ride.search_deadline and await self._offer_to_nearest(ride, now):
            return
        no_driver = next_status(ride.status, RideCommand.MARK_NO_DRIVER, SYSTEM_ACTOR)
        await self._offers.move_ride(ride.id, from_status=ride.status, to_status=no_driver, now=now)
        await self._session.refresh(ride)

    async def _offer_to_nearest(self, ride: Ride, now: datetime) -> bool:
        """Offer the ride to the nearest candidate; ``False`` only if there is none.

        If every candidate found was reserved by a concurrent search in the
        meantime (a unique index refuses the offer), the ride stays searching
        and the next pass tries again.
        """
        candidates = await find_nearby_candidates(
            self._session,
            pickup_of(ride),
            now=now,
            radius_m=self._policy.radius_m,
            max_location_age_s=self._policy.max_location_age_s,
            for_ride_id=ride.id,
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
                expires_at=now + self._policy.offer_ttl,
                responded_at=None,
            )
            if await self._offers.try_add_offer(offer):
                return True
        return True


async def revoke_pending_offers(session: AsyncSession, ride_id: uuid.UUID, now: datetime) -> int:
    """Revoke the ride's pending offer inside the caller's write transaction (cancel, T07B).

    Lock the ride first (rides -> ride_offers). Returns how many offers changed.
    """
    return await OfferRepository(session).decide_pending_of_ride(ride_id, _REVOKED, now)


async def revoke_driver_offers(session: AsyncSession, driver_id: uuid.UUID, now: datetime) -> int:
    """Revoke the driver's pending offer inside the caller's transaction (offline, unapproved).

    The ride stays ``searching`` without a pending offer; the next loop pass
    (or ``process_ride``) asks the next candidate.
    """
    return await OfferRepository(session).decide_pending_of_driver(driver_id, _REVOKED, now)


def restart_search(ride: Ride, now: datetime, policy: DispatchPolicy) -> None:
    """Open a new search window on a ride that returns to ``searching`` (release, T07B).

    Set it inside the caller's transaction together with the status change,
    then call ``DispatchService.process_ride`` after commit. Drivers who had
    any offer for this ride, the releasing driver included, stay excluded.
    """
    ride.search_started_at = now
    ride.search_deadline = now + policy.search_budget
