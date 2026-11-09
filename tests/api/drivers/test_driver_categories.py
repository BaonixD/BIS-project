import uuid

import httpx
import pytest

from support.auth import register_and_login
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import NEAR_PICKUP
from support.rides import order_ride
from taxi_service.modules.rides.states import OfferStatus
from taxi_service.modules.rides.tariffs import Tariff


async def choose(client: httpx.AsyncClient, categories: list[str]) -> httpx.Response:
    driver = await login_as(client, "multi_driver")
    return await client.put(
        "/api/v1/drivers/me/availability",
        json={"online": True, "categories": categories},
        headers=driver.csrf_headers,
    )


async def test_business_automatically_allows_every_tariff(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.driver("multi_driver", car_class=Tariff.BUSINESS, online=False)
    await login_as(client, "multi_driver")
    body = (await client.get("/api/v1/drivers/me")).json()
    assert body["vehicle"]["categories"] == ["economy", "comfort", "comfort_plus", "business"]
    assert body["enabled_categories"] == body["vehicle"]["categories"]


async def test_driver_selects_working_tariffs_without_changing_car_class(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    await driver_factory.driver("multi_driver", car_class=Tariff.BUSINESS, online=False)
    response = await choose(client, ["comfort_plus", "economy"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["online"] is True
    assert body["enabled_categories"] == ["economy", "comfort_plus"]
    assert body["vehicle"]["car_class"] == "business"
    assert body["vehicle"]["categories"] == ["economy", "comfort", "comfort_plus", "business"]
    driver = await login_as(client, "multi_driver")
    await client.put(
        "/api/v1/drivers/me/availability", json={"online": False}, headers=driver.csrf_headers
    )
    assert (await client.get("/api/v1/drivers/me")).json()["enabled_categories"] == [
        "economy",
        "comfort_plus",
    ]


@pytest.mark.parametrize(
    ("tariff", "eligible"),
    [("economy", True), ("comfort", False), ("comfort_plus", True), ("business", False)],
)
async def test_dispatch_matches_driver_preferences(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    tariff: str,
    eligible: bool,
) -> None:
    driver_id = await driver_factory.driver(
        "multi_driver", location=NEAR_PICKUP, car_class=Tariff.BUSINESS
    )
    assert (await choose(client, ["economy", "comfort_plus"])).status_code == 200
    passenger = await register_and_login(client, "passenger")
    ride = await order_ride(client, passenger, tariff=tariff)
    offers = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert bool(offers) is eligible
    if eligible:
        assert offers[0].driver_id == driver_id


@pytest.mark.parametrize(
    "categories", [[], ["economy", "economy"], ["premium"], None, ["business"]]
)
async def test_invalid_or_above_class_selection_is_rejected(
    client: httpx.AsyncClient, driver_factory: DriverFactory, categories: list[str] | None
) -> None:
    await driver_factory.driver("multi_driver", car_class=Tariff.COMFORT, online=False)
    driver = await login_as(client, "multi_driver")
    response = await client.put(
        "/api/v1/drivers/me/availability",
        json={"online": True, "categories": categories},
        headers=driver.csrf_headers,
    )
    assert response.status_code == 422
    stored = (await client.get("/api/v1/drivers/me")).json()
    assert stored["online"] is False
    assert stored["enabled_categories"] == ["economy", "comfort"]


async def test_removing_working_tariff_revokes_only_ineligible_offer(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("multi_driver", location=NEAR_PICKUP, car_class=Tariff.BUSINESS)
    assert (await choose(client, ["economy", "comfort_plus"])).status_code == 200
    passenger = await register_and_login(client, "passenger")
    ride = await order_ride(client, passenger, tariff="comfort_plus")
    ride_id = uuid.UUID(ride["id"])
    assert (await dispatcher.offers(ride_id))[0].status is OfferStatus.PENDING
    assert (await choose(client, ["comfort_plus", "business"])).status_code == 200
    assert (await dispatcher.offers(ride_id))[0].status is OfferStatus.PENDING
    assert (await choose(client, ["economy", "business"])).status_code == 200
    assert (await dispatcher.offers(ride_id))[0].status is OfferStatus.REVOKED


async def test_class_downgrade_removes_unavailable_working_tariffs(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    driver_id = await driver_factory.driver("multi_driver", car_class=Tariff.BUSINESS)
    await choose(client, ["business"])
    admin = await login_as(client, "admin")
    response = await client.patch(
        f"/api/v1/admin/drivers/{driver_id}",
        json={"car_class": "comfort"},
        headers=admin.csrf_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["online"] is False
    assert body["enabled_categories"] == ["economy", "comfort"]
    assert body["vehicle"]["categories"] == ["economy", "comfort"]


async def test_class_upgrade_keeps_explicit_driver_opt_outs(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
) -> None:
    driver_id = await driver_factory.driver("multi_driver", car_class=Tariff.COMFORT)
    await choose(client, ["economy"])
    admin = await login_as(client, "admin")
    response = await client.patch(
        f"/api/v1/admin/drivers/{driver_id}",
        json={"car_class": "business"},
        headers=admin.csrf_headers,
    )
    assert response.status_code == 200
    assert response.json()["vehicle"]["categories"] == [
        "economy",
        "comfort",
        "comfort_plus",
        "business",
    ]
    assert response.json()["enabled_categories"] == ["economy"]


async def test_working_tariff_change_does_not_cancel_an_accepted_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
) -> None:
    driver_id = await driver_factory.driver(
        "multi_driver", location=NEAR_PICKUP, car_class=Tariff.BUSINESS
    )
    passenger = await register_and_login(client, "passenger")
    ride = await order_ride(client, passenger, tariff="comfort")
    ride_id = uuid.UUID(ride["id"])
    [offer] = await dispatcher.offers(ride_id)
    await dispatcher.accept(offer.id, driver_id)
    assert (await choose(client, ["business"])).status_code == 200
    accepted = await dispatcher.ride(ride_id)
    assert accepted.status.value == "assigned"
    assert accepted.driver_id == driver_id
