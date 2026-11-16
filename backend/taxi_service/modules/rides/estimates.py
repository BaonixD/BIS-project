import asyncio
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.drivers.geodesy import haversine_m
from taxi_service.modules.drivers.models import DriverProfile
from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.exceptions import (
    RouteNotFoundError,
    RoutingProviderError,
    RoutingUnavailableError,
)
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.rides.exceptions import RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.service import can_view_ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole


class RideEstimateResponse(BaseModel):
    ride_id: uuid.UUID
    ride_status: RideStatus
    driver_id: uuid.UUID | None
    generated_at: datetime
    trip_distance_m: int
    trip_duration_s: int
    target: Literal["pickup", "dropoff"] | None = None
    distance_m: int | None = None
    duration_s: int | None = None
    arrival_at: datetime | None = None
    source: Literal["road", "approximate", "unavailable"] = "unavailable"
    stale: bool = False
    location_updated_at: datetime | None = None
    route: RouteResult | None = None


class EstimateCache:
    def __init__(self, *, ttl_s: int = 15, capacity: int = 500) -> None:
        self.ttl_s = ttl_s
        self.capacity = capacity
        self.values: OrderedDict[tuple[object, ...], RideEstimateResponse] = OrderedDict()
        self.pending: dict[tuple[object, ...], asyncio.Task[RideEstimateResponse]] = {}

    async def get(
        self,
        key: tuple[object, ...],
        now: datetime,
        load: Callable[[], Awaitable[RideEstimateResponse]],
    ) -> RideEstimateResponse:
        cached = self.values.get(key)
        if cached is not None and (now - cached.generated_at).total_seconds() < self.ttl_s:
            self.values.move_to_end(key)
            return cached.model_copy()
        task = self.pending.get(key)
        if task is None:
            task = asyncio.create_task(self._load(key, load))
            self.pending[key] = task
        return (await asyncio.shield(task)).model_copy()

    async def _load(
        self, key: tuple[object, ...], load: Callable[[], Awaitable[RideEstimateResponse]]
    ) -> RideEstimateResponse:
        try:
            result = await load()
            if result.source == "road":
                self.values[key] = result
                self.values.move_to_end(key)
                while len(self.values) > self.capacity:
                    self.values.popitem(last=False)
            return result
        finally:
            self.pending.pop(key, None)

    async def close(self) -> None:
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.pending.clear()
        self.values.clear()


async def _snapshot(
    db: AsyncSession, ride_id: uuid.UUID, user_id: uuid.UUID, role: UserRole, clock: Clock
) -> tuple[RideEstimateResponse, Coordinates | None, Coordinates | None]:
    async with read_transaction(db):
        ride = await db.scalar(
            select(Ride).where(Ride.id == ride_id).execution_options(populate_existing=True)
        )
        if ride is None or not can_view_ride(ride, user_id, role):
            raise RideNotFoundError
        result = RideEstimateResponse(
            ride_id=ride.id,
            ride_status=ride.status,
            driver_id=ride.driver_id,
            generated_at=clock.now(),
            trip_distance_m=ride.distance_m,
            trip_duration_s=ride.duration_s,
        )
        if (
            ride.status not in (RideStatus.ASSIGNED, RideStatus.IN_PROGRESS)
            or ride.driver_id is None
        ):
            return result, None, None
        result.target = "pickup" if ride.status is RideStatus.ASSIGNED else "dropoff"
        destination = (
            Coordinates(latitude=ride.pickup_latitude, longitude=ride.pickup_longitude)
            if result.target == "pickup"
            else Coordinates(latitude=ride.dropoff_latitude, longitude=ride.dropoff_longitude)
        )
        profile = await db.scalar(
            select(DriverProfile)
            .where(DriverProfile.user_id == ride.driver_id)
            .execution_options(populate_existing=True)
        )
        if profile is None:
            return result, None, destination
        result.location_updated_at = profile.location_updated_at
        if (
            profile.location_updated_at is None
            or (clock.now() - profile.location_updated_at).total_seconds() > 60
        ):
            result.stale = True
            return result, None, destination
        if profile.latitude is None or profile.longitude is None:
            return result, None, destination
        return (
            result,
            Coordinates(latitude=profile.latitude, longitude=profile.longitude),
            destination,
        )


async def estimate(
    db: AsyncSession,
    ride_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    clock: Clock,
    routing: RoutingProvider,
    cache: EstimateCache,
) -> RideEstimateResponse:
    result, origin, destination = await _snapshot(db, ride_id, user_id, role, clock)
    if origin is None or destination is None:
        return result
    key = (ride_id, result.driver_id, result.ride_status, result.location_updated_at)

    async def load() -> RideEstimateResponse:
        value = result.model_copy()
        try:
            if origin == destination:
                value.distance_m = value.duration_s = 0
            else:
                route = await routing.get_route(origin, destination)
                value.distance_m, value.duration_s = route.distance_m, route.duration_s
                value.route = route
            value.source = "road"
        except RouteNotFoundError:
            return value
        except (RoutingUnavailableError, RoutingProviderError):
            value.distance_m = round(haversine_m(origin, destination) * 1.3)
            value.duration_s = round(value.distance_m / (25000 / 3600))
            value.source = "approximate"
        value.generated_at = clock.now()
        value.arrival_at = value.generated_at + timedelta(seconds=value.duration_s)
        return value

    calculated = await cache.get(key, clock.now(), load)
    current, _, _ = await _snapshot(db, ride_id, user_id, role, clock)
    if (current.driver_id, current.ride_status) != (result.driver_id, result.ride_status):
        return current
    calculated.stale = current.stale or (clock.now() - calculated.generated_at).total_seconds() > 60
    return calculated
