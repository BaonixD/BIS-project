import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, Query
from pydantic import AwareDatetime, BaseModel

from taxi_service.core.errors import AppError
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.payments.rules import PaymentMethod, PaymentStatus
from taxi_service.modules.rides.queries import RideFilters, RidePage, RideRow
from taxi_service.modules.rides.schemas import dropoff_of, pickup_of
from taxi_service.modules.rides.states import RideStatus
from taxi_service.schemas.pagination import Page, PageParams


class RideSummary(BaseModel):
    """A ride in a list: points, metrics, price and payment, without the route geometry.

    ``payment_status`` and ``payment_method`` are null until the ride is completed.
    """

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


class InvalidDateRangeError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="invalid_date_range",
            message="created_from must not be later than created_to.",
        )


def ride_filters(
    status: Annotated[
        list[RideStatus] | None,
        Query(description="Only rides in these statuses; repeat the parameter for several."),
    ] = None,
    created_from: Annotated[
        AwareDatetime | None,
        Query(description="Created at or after this time (inclusive); ISO 8601 with offset."),
    ] = None,
    created_to: Annotated[
        AwareDatetime | None,
        Query(description="Created before this time (exclusive); ISO 8601 with offset."),
    ] = None,
) -> RideFilters:
    """Query filters of ride lists; 422 ``invalid_date_range`` when the bounds are reversed."""
    if created_from is not None and created_to is not None and created_from > created_to:
        raise InvalidDateRangeError
    return RideFilters(
        statuses=frozenset(status or ()), created_from=created_from, created_to=created_to
    )


RideFiltersDep = Annotated[RideFilters, Depends(ride_filters)]
