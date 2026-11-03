import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from taxi_service.modules.drivers.models import DriverProfile
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.payments.rules import PaymentMethod, PaymentStatus
from taxi_service.modules.rides.history import RidePage, RideRow
from taxi_service.modules.rides.models import (
    REASON_MAX_LENGTH,
    Ride,
    RideOffer,
    RideQuote,
    RouteSnapshot,
)
from taxi_service.modules.rides.states import OfferStatus, RideStatus
from taxi_service.schemas.pagination import Page, PageParams


class QuoteRequest(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


class ReleaseRequest(BaseModel):
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


class VehicleCard(BaseModel):
    make: str
    model: str
    color: str
    plate_number: str


class DriverCard(BaseModel):
    """``location`` is the last one sent; a stale one never ends the ride."""

    full_name: str | None
    phone: str | None
    vehicle: VehicleCard | None
    location: Coordinates | None
    location_updated_at: datetime | None

    @classmethod
    def build(cls, profile: DriverProfile) -> "DriverCard":
        vehicle = profile.vehicle
        location = None
        if profile.longitude is not None and profile.latitude is not None:
            location = Coordinates(longitude=profile.longitude, latitude=profile.latitude)
        return cls(
            full_name=profile.full_name,
            phone=profile.phone,
            vehicle=None
            if vehicle is None
            else VehicleCard(
                make=vehicle.make,
                model=vehicle.model,
                color=vehicle.color,
                plate_number=vehicle.plate_number,
            ),
            location=location,
            location_updated_at=profile.location_updated_at,
        )


class RideDetailsResponse(RideResponse):
    driver: DriverCard | None = Field(
        description="Only for the passenger and the driver while the ride is assigned, "
        "arrived or in_progress; otherwise null."
    )

    @classmethod
    def with_driver(cls, ride: Ride, driver: DriverProfile | None) -> "RideDetailsResponse":
        card = None if driver is None else DriverCard.build(driver)
        return cls(**RideResponse.build(ride).model_dump(), driver=card)


class OfferResponse(BaseModel):
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


class RideSummary(BaseModel):
    """A list item without the route geometry; payment fields are null before completion."""

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
    payment_status: PaymentStatus | None
    payment_method: PaymentMethod | None

    @classmethod
    def build(cls, row: RideRow) -> "RideSummary":
        ride = row.ride
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
            payment_status=row.payment_status,
            payment_method=row.payment_method,
        )

    @classmethod
    def page(cls, result: RidePage, params: PageParams) -> Page["RideSummary"]:
        return Page(
            items=[cls.build(row) for row in result.rows],
            limit=params.limit,
            offset=params.offset,
            total=result.total,
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
