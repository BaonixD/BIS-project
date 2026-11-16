from datetime import timedelta

import httpx

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import NEAR_PICKUP
from support.rides import order_ride
from support.routing import FakeRoutingProvider
from taxi_service.modules.geo.exceptions import RouteNotFoundError, RoutingUnavailableError


async def test_estimate_permissions_cache_fallback_and_stale_location(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
    routing_provider: FakeRoutingProvider,
) -> None:
    import uuid

    driver_id = await driver_factory.driver("driver", location=NEAR_PICKUP)
    passenger = await register_and_login(client, "passenger")
    ride = await order_ride(client, passenger)
    [offer] = await dispatcher.offers(uuid.UUID(ride["id"]))
    await dispatcher.accept(offer.id, driver_id)
    url = f"/api/v1/rides/{ride['id']}/estimate"
    count = routing_provider.call_count
    result = await client.get(url)
    assert result.status_code == 200
    body = result.json()
    assert body["target"] == "pickup"
    assert body["source"] == "road"
    assert body["distance_m"] == 10000
    assert (await client.get(url)).json()["arrival_at"] == body["arrival_at"]
    assert routing_provider.call_count == count + 1
    clock.advance(timedelta(seconds=16))
    routing_provider.fail_with(RoutingUnavailableError())
    assert (await client.get(url)).json()["source"] == "approximate"
    routing_provider.fail_with(RouteNotFoundError())
    assert (await client.get(url)).json()["source"] == "unavailable"
    clock.advance(timedelta(seconds=60))
    assert (await client.get(url)).json()["stale"] is True
    await register_and_login(client, "outsider")
    assert (await client.get(url)).status_code == 404
    await login_as(client, "admin")
    assert (await client.get(url)).status_code == 200


async def test_in_progress_estimates_destination_and_stops_after_completion(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    routing_provider: FakeRoutingProvider,
) -> None:
    from support.lifecycle import send, trip_in

    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    url = f"/api/v1/rides/{trip.ride_id}/estimate"
    result = await client.get(url)
    assert result.json()["target"] == "dropoff"
    assert result.json()["source"] == "road"
    await send(client, trip.ride_id, "complete", trip.driver)
    count = routing_provider.call_count
    result = await client.get(url)
    assert result.json()["target"] is None
    assert result.json()["arrival_at"] is None
    assert routing_provider.call_count == count
