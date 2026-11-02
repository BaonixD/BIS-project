"""The ``ride_factory`` helper creates real rows through the services (for T06 tests)."""

from support.rides import PICKUP, RideFactory, count_rows
from taxi_service.database.session import SessionFactory
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.models import IdempotencyRecord, Ride, RideQuote
from taxi_service.modules.rides.states import RideStatus


async def test_searching_rides_for_new_passengers(
    ride_factory: RideFactory, session_factory: SessionFactory
) -> None:
    pickup = Coordinates(longitude=76.95, latitude=43.25)

    first = await ride_factory.searching_ride(pickup=pickup)
    second = await ride_factory.searching_ride()

    assert first.passenger_id != second.passenger_id
    assert (first.status, first.driver_id, first.amount_kzt) == (RideStatus.SEARCHING, None, 2200)
    assert (first.pickup_longitude, first.pickup_latitude) == pickup.as_lon_lat()
    assert (second.pickup_longitude, second.pickup_latitude) == PICKUP.as_lon_lat()
    for model in (Ride, RideQuote, IdempotencyRecord):
        assert await count_rows(session_factory, model) == 2


async def test_ride_for_a_given_passenger(ride_factory: RideFactory) -> None:
    passenger_id = await ride_factory.passenger("pat")

    ride = await ride_factory.searching_ride(passenger_id)

    assert ride.passenger_id == passenger_id
