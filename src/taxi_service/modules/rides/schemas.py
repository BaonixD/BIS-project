import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.rides.models import REASON_MAX_LENGTH, Ride, RideQuote, RouteSnapshot
from taxi_service.modules.rides.states import RideStatus


class QuoteRequest(BaseModel):
    """Two different points; the price comes from the server, never from the client."""

    model_config = ConfigDict(extra="forbid")

    pickup: Coordinates
    dropoff: Coordinates


class QuoteResponse(BaseModel):
    quote_id: uuid.UUID
    pickup: Coordinates
    dropoff: Coordinates
    route: RouteResult
    amount_kzt: int
    currency: Literal["KZT"]
    tariff_version: str
    created_at: datetime
    expires_at: datetime

    @classmethod
    def build(cls, quote: RideQuote) -> "QuoteResponse":
        return cls(
            quote_id=quote.id,
            pickup=pickup_of(quote),
            dropoff=dropoff_of(quote),
            route=route_of(quote),
            amount_kzt=quote.amount_kzt,
            currency="KZT",
            tariff_version=quote.tariff_version,
            created_at=quote.created_at,
            expires_at=quote.expires_at,
        )


class RideCreateRequest(BaseModel):
    """Only the quote: route, price and status are the server's (extra fields are 422)."""

    model_config = ConfigDict(extra="forbid")

    quote_id: uuid.UUID


def _without_control_characters(value: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Reason must not contain control characters")
    return value


Reason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH),
    AfterValidator(_without_control_characters),
    Field(description="Plain text, 1 to 200 characters after trimming, no control characters."),
]


class CancelRequest(BaseModel):
    """Optional body of ``cancel``; the reason is stored with the ride and in its history."""

    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


class ReleaseRequest(BaseModel):
    """Body of ``release``: why the driver gives the ride up (kept in the ride history)."""

    model_config = ConfigDict(extra="forbid")

    reason: Reason


class RideResponse(BaseModel):
    id: uuid.UUID
    status: RideStatus
    passenger_id: uuid.UUID
    driver_id: uuid.UUID | None
    quote_id: uuid.UUID
    pickup: Coordinates
    dropoff: Coordinates
    route: RouteResult
    amount_kzt: int
    currency: Literal["KZT"]
    tariff_version: str
    created_at: datetime
    updated_at: datetime
    assigned_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None

    @classmethod
    def build(cls, ride: Ride) -> "RideResponse":
        return cls(
            id=ride.id,
            status=ride.status,
            passenger_id=ride.passenger_id,
            driver_id=ride.driver_id,
            quote_id=ride.quote_id,
            pickup=pickup_of(ride),
            dropoff=dropoff_of(ride),
            route=route_of(ride),
            amount_kzt=ride.amount_kzt,
            currency="KZT",
            tariff_version=ride.tariff_version,
            created_at=ride.created_at,
            updated_at=ride.updated_at,
            assigned_at=ride.assigned_at,
            arrived_at=ride.arrived_at,
            started_at=ride.started_at,
            completed_at=ride.completed_at,
            cancelled_at=ride.cancelled_at,
            cancel_reason=ride.cancel_reason,
        )


def pickup_of(snapshot: RouteSnapshot) -> Coordinates:
    return Coordinates(longitude=snapshot.pickup_longitude, latitude=snapshot.pickup_latitude)


def dropoff_of(snapshot: RouteSnapshot) -> Coordinates:
    return Coordinates(longitude=snapshot.dropoff_longitude, latitude=snapshot.dropoff_latitude)


def route_of(snapshot: RouteSnapshot) -> RouteResult:
    return RouteResult.model_validate(
        {
            "distance_m": snapshot.distance_m,
            "duration_s": snapshot.duration_s,
            "route_geometry": snapshot.route_geometry,
            "provider": snapshot.provider,
        }
    )
