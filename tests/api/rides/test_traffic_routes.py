import httpx

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.lifecycle import trip_in
from support.rides import ABAY_DOSTYK, AL_FARABI, RIDES_URL, request_quote, ride_body, ride_headers
from support.routing import FakeRoutingProvider, fake_route
from taxi_service.modules.geo.schemas import Coordinates, RouteResult


def traffic_route(clock: ManualClock) -> RouteResult:
    return fake_route(Coordinates(**ABAY_DOSTYK), Coordinates(**AL_FARABI)).model_copy(
        update={
            "provider": "mapbox",
            "duration_s": 3600,
            "duration_typical_s": 1500,
            "traffic_mode": "live_or_typical",
            "generated_at": clock.now(),
        }
    )


async def test_quote_copies_traffic_snapshot_and_all_four_fares_into_order(
    client: httpx.AsyncClient,
    routing_provider: FakeRoutingProvider,
    clock: ManualClock,
) -> None:
    routing_provider.route = traffic_route(clock)
    passenger = await register_and_login(client, "traffic_passenger")
    quote = await request_quote(client, passenger)
    assert quote["route"]["duration_s"] == 3600
    assert quote["route"]["duration_typical_s"] == 1500
    assert quote["route"]["traffic_mode"] == "live_or_typical"
    assert len(quote["options"]) == 4
    response = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], tariff="business"),
        headers=ride_headers(passenger),
    )
    assert response.status_code == 201
    ride = response.json()
    assert ride["route"] == quote["route"]
    assert ride["amount_kzt"] == next(
        item["amount_kzt"] for item in quote["options"] if item["tariff"] == "business"
    )


async def test_live_estimate_returns_its_own_geometry_but_never_reprices_order(
    client: httpx.AsyncClient,
    routing_provider: FakeRoutingProvider,
    clock: ManualClock,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
) -> None:
    routing_provider.route = traffic_route(clock)
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    before = (await client.get(f"{RIDES_URL}/{trip.ride_id}")).json()
    updated = traffic_route(clock).model_copy(update={"duration_s": 1800, "distance_m": 6000})
    routing_provider.route = updated
    response = await client.get(f"{RIDES_URL}/{trip.ride_id}/estimate")
    assert response.status_code == 200
    estimate = response.json()
    assert estimate["source"] == "road"
    assert estimate["duration_s"] == estimate["route"]["duration_s"] == 1800
    assert estimate["distance_m"] == estimate["route"]["distance_m"] == 6000
    assert estimate["route"] == updated.model_dump(mode="json")
    after = (await client.get(f"{RIDES_URL}/{trip.ride_id}")).json()
    assert after["amount_kzt"] == before["amount_kzt"]
    assert after["route"] == before["route"]
    assert after["route"]["duration_s"] == 3600
