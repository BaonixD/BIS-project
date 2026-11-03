import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from taxi_service.modules.drivers.models import DriverProfile
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.payments.models import PaymentMethod, PaymentStatus
from taxi_service.modules.ratings.models import RideRating
from taxi_service.modules.ratings.records import NO_RATINGS, RatingSummary
from taxi_service.modules.ratings.schemas import MyRating, RatingSummaryResponse
from taxi_service.modules.rides.history import RidePage, RideRow
from taxi_service.modules.rides.models import (
    REASON_MAX_LENGTH,
    Ride,
    RideOffer,
    RideQuote,
    RouteSnapshot,
)
from taxi_service.modules.rides.states import OfferStatus, RideStatus
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.schemas.pagination import Page, PageParams


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup: Coordinates
    dropoff: Coordinates


class TariffOption(BaseModel):
    tariff: Tariff
    amount_kzt: int


class QuoteResponse(BaseModel):
    quote_id: uuid.UUID
    pickup: Coordinates
    dropoff: Coordinates
    route: RouteResult
    options: list[TariffOption] = Field(
        description="Every tariff, cheapest first: economy, comfort, comfort_plus, business."
    )
    currency: Literal["KZT"]
    tariff_version: str
    kaspi_payment_url: str | None = Field(
        description="The configured Kaspi link (pay.kaspi.kz) or null when Kaspi is off. "
        "Opening it charges nothing: a Kaspi ride counts as paid once a driver accepts it."
    )
    created_at: datetime
    expires_at: datetime

    @classmethod
    def build(cls, quote: RideQuote, *, kaspi_payment_url: str | None) -> "QuoteResponse":
        return cls(
            quote_id=quote.id,
            pickup=pickup_of(quote),
            dropoff=dropoff_of(quote),
            route=route_of(quote),
            options=[
                TariffOption(tariff=tariff, amount_kzt=amount)
                for tariff, amount in quote.amounts().items()
            ],
            currency="KZT",
            tariff_version=quote.tariff_version,
            kaspi_payment_url=kaspi_payment_url,
            created_at=quote.created_at,
            expires_at=quote.expires_at,
        )


class RideCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote_id: uuid.UUID
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.CASH,
        description="Chosen with the order. kaspi_link needs KASPI_PAYMENT_URL and counts as "
        "paid when a driver accepts the ride (a simulated charge, no money is checked); "
        "its link is kaspi_payment_url of the quote and payment_url of "
        "GET /rides/{ride_id}/payment.",
    )
    tariff: Tariff = Field(
        default=Tariff.ECONOMY,
        description="The ride costs this tariff's amount from the quote; only cars of this "
        "class or higher are offered the ride.",
    )


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
    tariff: Tariff
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
    payment_method: PaymentMethod | None
    payment_status: PaymentStatus | None

    @classmethod
    def build(cls, ride: Ride) -> "RideResponse":
        payment = ride.payment
        return cls(
            id=ride.id,
            status=ride.status,
            passenger_id=ride.passenger_id,
            driver_id=ride.driver_id,
            quote_id=ride.quote_id,
            pickup=pickup_of(ride),
            dropoff=dropoff_of(ride),
            route=route_of(ride),
            tariff=ride.tariff,
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
            payment_method=None if payment is None else payment.method,
            payment_status=None if payment is None else payment.status,
        )


class VehicleCard(BaseModel):
    make: str
    model: str
    color: str
    plate_number: str
    car_class: Tariff


class DriverCard(BaseModel):
    """``location`` is the last one sent; a stale one never ends the ride."""

    full_name: str | None
    phone: str | None
    vehicle: VehicleCard | None
    location: Coordinates | None
    location_updated_at: datetime | None
    rating: RatingSummaryResponse = Field(description="Stars the driver received.")

    @classmethod
    def build(cls, profile: DriverProfile, rating: RatingSummary) -> "DriverCard":
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
                car_class=vehicle.car_class,
            ),
            location=location,
            location_updated_at=profile.location_updated_at,
            rating=RatingSummaryResponse.build(rating),
        )


class RideDetailsResponse(RideResponse):
    driver: DriverCard | None = Field(
        description="Only for the passenger and the driver while the ride is assigned, "
        "arrived or in_progress; otherwise null."
    )
    my_rating: MyRating | None = Field(
        description="The rating the caller gave this ride; null until they rate it "
        "(always null for an admin)."
    )

    @classmethod
    def build_details(
        cls,
        ride: Ride,
        driver: DriverProfile | None,
        driver_rating: RatingSummary | None,
        my_rating: RideRating | None,
    ) -> "RideDetailsResponse":
        card = None
        if driver is not None:
            card = DriverCard.build(driver, driver_rating or NO_RATINGS)
        return cls(
            **RideResponse.build(ride).model_dump(),
            driver=card,
            my_rating=None if my_rating is None else MyRating.build(my_rating),
        )


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
    tariff: Tariff
    passenger_rating: RatingSummaryResponse = Field(description="Stars the passenger received.")
    created_at: datetime
    expires_at: datetime

    @classmethod
    def build(
        cls, offer: RideOffer, ride: Ride, passenger_rating: RatingSummary
    ) -> "OfferResponse":
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
            tariff=ride.tariff,
            passenger_rating=RatingSummaryResponse.build(passenger_rating),
            created_at=offer.created_at,
            expires_at=offer.expires_at,
        )


class RideSummary(BaseModel):
    """A list item without the route geometry; payment fields are null only without a payment."""

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
    tariff: Tariff
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
            tariff=ride.tariff,
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
