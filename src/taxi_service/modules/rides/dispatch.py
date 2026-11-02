"""Driver search: one offer at a time to the nearest candidate (MVP_SPEC §6, ADR 0006)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.modules.rides.models import Ride, RideOffer
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy


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

    async def process_ride(self, ride_id: uuid.UUID) -> Ride | None:
        raise NotImplementedError

    async def process_due(self) -> int:
        raise NotImplementedError

    async def accept_offer(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> Ride:
        raise NotImplementedError

    async def reject_offer(self, offer_id: uuid.UUID, driver_id: uuid.UUID) -> RideOffer:
        raise NotImplementedError

    async def pending_offers(self, driver_id: uuid.UUID, *, limit: int, offset: int) -> OfferPage:
        raise NotImplementedError


async def revoke_pending_offers(session: AsyncSession, ride_id: uuid.UUID, now: datetime) -> int:
    raise NotImplementedError


def restart_search(ride: Ride, now: datetime, policy: DispatchPolicy) -> None:
    raise NotImplementedError
