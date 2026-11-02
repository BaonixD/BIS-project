import uuid
from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.geo.service import plan_road_route
from taxi_service.modules.rides.models import RideQuote
from taxi_service.modules.rides.pricing import Fare, calculate_fare
from taxi_service.modules.rides.repository import RideRepository
from taxi_service.modules.rides.schemas import QuoteRequest

QUOTE_TTL: Final = timedelta(minutes=5)


class RideService:
    """Quotes and ride creation of a passenger; callers pass the passenger's user id."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock
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
