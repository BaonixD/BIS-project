import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.models import Ride, RideOffer
from taxi_service.modules.rides.schemas import dropoff_of, pickup_of
from taxi_service.modules.rides.states import OfferStatus


class OfferResponse(BaseModel):
    """An offer with what the driver needs to decide: points, road route length and price."""

    id: uuid.UUID
    ride_id: uuid.UUID
    status: OfferStatus
    pickup: Coordinates
    dropoff: Coordinates
    distance_m: int
    duration_s: int
    amount_kzt: int
    currency: Literal["KZT"]
    created_at: datetime
    expires_at: datetime

    @classmethod
    def build(cls, offer: RideOffer, ride: Ride) -> "OfferResponse":
        return cls(
            id=offer.id,
            ride_id=ride.id,
            status=offer.status,
            pickup=pickup_of(ride),
            dropoff=dropoff_of(ride),
            distance_m=ride.distance_m,
            duration_s=ride.duration_s,
            amount_kzt=ride.amount_kzt,
            currency="KZT",
            created_at=offer.created_at,
            expires_at=offer.expires_at,
        )
