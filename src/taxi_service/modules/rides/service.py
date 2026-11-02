import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.geo.service import plan_road_route
from taxi_service.modules.rides.exceptions import (
    ActiveRideExistsError,
    IdempotencyKeyReusedError,
    QuoteAlreadyUsedError,
    QuoteExpiredError,
    QuoteNotFoundError,
    RideNotFoundError,
)
from taxi_service.modules.rides.idempotency import request_fingerprint
from taxi_service.modules.rides.models import IdempotencyRecord, Ride, RideQuote
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.pricing import Fare, calculate_fare
from taxi_service.modules.rides.repository import RideRepository
from taxi_service.modules.rides.schemas import QuoteRequest, RideCreateRequest
from taxi_service.modules.users.models import UserRole

QUOTE_TTL: Final = timedelta(minutes=5)
CREATE_RIDE_OPERATION: Final = "create_ride"


@dataclass(frozen=True, slots=True)
class RideCreation:
    """``replayed`` is true when an earlier request with the same key created ``ride``."""

    ride: Ride
    replayed: bool


class RideService:
    """Quotes and ride creation of a passenger; callers pass the passenger's user id."""

    def __init__(
        self,
        session: AsyncSession,
        clock: Clock,
        policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    ) -> None:
        self._session = session
        self._clock = clock
        self._policy = policy
        self._rides = RideRepository(session)

    async def create_quote(
        self, passenger_id: uuid.UUID, request: QuoteRequest, routing: RoutingProvider
    ) -> RideQuote:
        """Road route first (no transaction is open), then a short write of the quote.

        Routing errors propagate unchanged and store nothing. The five minutes
        of validity start once the route is known.
        """
        route = await plan_road_route(routing, request.pickup, request.dropoff)
        fare = calculate_fare(distance_m=route.distance_m, duration_s=route.duration_s)
        now = self._clock.now()
        quote = RideQuote(
            id=uuid.uuid4(),
            passenger_id=passenger_id,
            **route_snapshot(request.pickup, request.dropoff, route, fare),
            created_at=now,
            expires_at=now + QUOTE_TTL,
        )
        async with self._session.begin():
            await self._rides.add_quote(quote)
        return quote

    async def create_ride(
        self, passenger_id: uuid.UUID, request: RideCreateRequest, key: str
    ) -> RideCreation:
        """Create a ``searching`` ride from the passenger's own valid quote, once per key.

        One write transaction: replay or 409 for a known key, then the quote and
        active-ride checks, then the ride and its idempotency record. If a
        concurrent request wins a unique constraint first, the same answers are
        derived from what it committed.
        """
        fingerprint = request_fingerprint(request.model_dump(mode="json"))
        try:
            async with self._session.begin():
                replayed = await self._replay(passenger_id, key, fingerprint)
                if replayed is not None:
                    return RideCreation(replayed, replayed=True)
                ride = await self._ride_from_quote(passenger_id, request.quote_id)
                await self._rides.add_idempotency_record(
                    IdempotencyRecord(
                        id=uuid.uuid4(),
                        user_id=passenger_id,
                        operation=CREATE_RIDE_OPERATION,
                        key=key,
                        request_fingerprint=fingerprint,
                        resource_id=ride.id,
                        created_at=ride.created_at,
                    )
                )
        except IntegrityError as error:
            return await self._after_conflict(passenger_id, request, key, fingerprint, error)
        return RideCreation(ride, replayed=False)

    async def get_ride(
        self, ride_id: uuid.UUID, *, viewer_id: uuid.UUID, viewer_role: UserRole
    ) -> Ride:
        """The ride for its passenger, its assigned driver or an admin; else 404."""
        async with read_transaction(self._session):
            ride = await self._rides.get_ride(ride_id)
        if ride is None or not can_view_ride(ride, viewer_id, viewer_role):
            raise RideNotFoundError
        return ride

    async def _replay(self, user_id: uuid.UUID, key: str, fingerprint: str) -> Ride | None:
        record = await self._rides.get_idempotency_record(user_id, CREATE_RIDE_OPERATION, key)
        if record is None:
            return None
        if record.request_fingerprint != fingerprint:
            raise IdempotencyKeyReusedError
        ride = await self._rides.get_ride(record.resource_id)
        if ride is None:
            raise RuntimeError("Idempotency record refers to a missing ride")
        return ride

    async def _ride_from_quote(self, passenger_id: uuid.UUID, quote_id: uuid.UUID) -> Ride:
        quote = await self._rides.get_quote(quote_id)
        if quote is None or quote.passenger_id != passenger_id:
            raise QuoteNotFoundError
        if await self._rides.quote_is_used(quote.id):
            raise QuoteAlreadyUsedError
        now = self._clock.now()
        if now >= quote.expires_at:
            raise QuoteExpiredError
        if await self._rides.has_active_ride(passenger_id):
            raise ActiveRideExistsError
        ride = Ride.from_quote(quote, now, search_budget=self._policy.search_budget)
        await self._rides.add_ride(ride)
        return ride

    async def _after_conflict(
        self,
        passenger_id: uuid.UUID,
        request: RideCreateRequest,
        key: str,
        fingerprint: str,
        error: IntegrityError,
    ) -> RideCreation:
        """Explain a lost constraint race with the rows the winner committed."""
        async with read_transaction(self._session):
            replayed = await self._replay(passenger_id, key, fingerprint)
            if replayed is not None:
                return RideCreation(replayed, replayed=True)
            if await self._rides.quote_is_used(request.quote_id):
                raise QuoteAlreadyUsedError from error
            if await self._rides.has_active_ride(passenger_id):
                raise ActiveRideExistsError from error
        raise error


def can_view_ride(ride: Ride, viewer_id: uuid.UUID, viewer_role: UserRole) -> bool:
    """Admins, the ride's passenger and the driver assigned now (not a released one)."""
    return viewer_role is UserRole.ADMIN or viewer_id in (ride.passenger_id, ride.driver_id)


def route_snapshot(
    pickup: Coordinates, dropoff: Coordinates, route: RouteResult, fare: Fare
) -> dict[str, Any]:
    """Column values of ``RouteSnapshot``."""
    return {
        "pickup_longitude": pickup.longitude,
        "pickup_latitude": pickup.latitude,
        "dropoff_longitude": dropoff.longitude,
        "dropoff_latitude": dropoff.latitude,
        "distance_m": route.distance_m,
        "duration_s": route.duration_s,
        "route_geometry": route.route_geometry.model_dump(mode="json"),
        "provider": route.provider,
        "amount_kzt": fare.amount_kzt,
        "currency": fare.currency,
        "tariff_version": fare.tariff_version,
    }
