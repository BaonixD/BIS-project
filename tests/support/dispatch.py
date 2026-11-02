"""Dispatch through the service, without HTTP: each call opens its own session.

Fixture ``dispatcher`` (test clock, default policy: 30 s offers, 180 s search)::

    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(timedelta(seconds=30))
    await dispatcher.process_due()          # what the background loop does every second

Through the API: ``OFFERS_URL`` (GET, driver), ``accept_url(id)`` and ``reject_url(id)``
(POST with the driver's CSRF header).

Several calls can run concurrently with ``asyncio.gather``: separate sessions and
connections, as separate requests would have.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from support.clock import ManualClock
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.rides.dispatch import DispatchService
from taxi_service.modules.rides.models import Ride, RideOffer
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.states import OfferStatus

OFFERS_URL = "/api/v1/drivers/me/offers"
RIDE_OFFERS_URL = "/api/v1/ride-offers"


def accept_url(offer_id: uuid.UUID | str) -> str:
    return f"{RIDE_OFFERS_URL}/{offer_id}/accept"


def reject_url(offer_id: uuid.UUID | str) -> str:
    return f"{RIDE_OFFERS_URL}/{offer_id}/reject"


@dataclass
class Dispatcher:
    session_factory: SessionFactory
    clock: ManualClock
    policy: DispatchPolicy = field(default=DEFAULT_DISPATCH_POLICY)

    async def process(self, ride_id: uuid.UUID) -> Ride | None:
        async with self.session_factory() as session:
            return await self._service(session).process_ride(ride_id)

    async def process_due(self) -> int:
        async with self.session_factory() as session:
            return await self._service(session).process_due()

    async def accept(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> Ride:
        async with self.session_factory() as session:
            return await self._service(session).accept_offer(offer_id, driver_id)

    async def reject(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> RideOffer:
        async with self.session_factory() as session:
            return await self._service(session).reject_offer(offer_id, driver_id)

    async def ride(self, ride_id: uuid.UUID) -> Ride:
        async with self.session_factory() as session, read_transaction(session):
            ride = await session.get(Ride, ride_id)
        assert ride is not None
        return ride

    async def offers(
        self, ride_id: uuid.UUID | None = None, *, driver_id: uuid.UUID | None = None
    ) -> list[RideOffer]:
        """Offers of a ride and/or a driver, oldest first."""
        query = select(RideOffer).order_by(RideOffer.created_at, RideOffer.id)
        if ride_id is not None:
            query = query.where(RideOffer.ride_id == ride_id)
        if driver_id is not None:
            query = query.where(RideOffer.driver_id == driver_id)
        async with self.session_factory() as session, read_transaction(session):
            return list(await session.scalars(query))

    async def pending(self, ride_id: uuid.UUID) -> RideOffer | None:
        """The single pending offer of a ride, if any."""
        pending = [
            offer for offer in await self.offers(ride_id) if offer.status is OfferStatus.PENDING
        ]
        assert len(pending) <= 1
        return pending[0] if pending else None

    def _service(self, session: AsyncSession) -> DispatchService:
        return DispatchService(session, self.clock, self.policy)
