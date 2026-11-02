import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.schemas import dropoff_of, pickup_of
from taxi_service.modules.rides.states import RideStatus


class RideSummary(BaseModel):
    """A ride in a list: points, metrics and price, without the route geometry."""

    id: uuid.UUID
    status: RideStatus
    passenger_id: uuid.UUID
    driver_id: uuid.UUID | None
    pickup: Coordinates
    dropoff: Coordinates
    distance_m: int
    duration_s: int
    amount_kzt: int
    currency: Literal["KZT"]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, ride: Ride) -> "RideSummary":
        return cls(
            id=ride.id,
            status=ride.status,
            passenger_id=ride.passenger_id,
            driver_id=ride.driver_id,
            pickup=pickup_of(ride),
            dropoff=dropoff_of(ride),
            distance_m=ride.distance_m,
            duration_s=ride.duration_s,
            amount_kzt=ride.amount_kzt,
            currency="KZT",
            created_at=ride.created_at,
            updated_at=ride.updated_at,
        )
