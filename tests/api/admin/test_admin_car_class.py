"""Vehicle class of a driver (ADR 0012): set by an admin, never by the driver."""

import uuid
from typing import Any

import httpx
import pytest

from support.auth import register_and_login
from support.dispatch import Dispatcher
from support.drivers import (
    ADMIN_DRIVERS_URL,
    DRIVERS_ME_URL,
    DriverFactory,
    approve_url,
    complete_profile,
    login_as,
    registered_driver,
    vehicle,
)
from support.lifecycle import NEAR_PICKUP
from support.rides import order_ride
from taxi_service.modules.rides.states import OfferStatus
from taxi_service.modules.rides.tariffs import Tariff


@pytest.fixture
async def admin_id(driver_factory: DriverFactory) -> uuid.UUID:
    """The ``admin`` account that also approves the factory's drivers."""
    return await driver_factory.admin_id()


def driver_url(driver_id: uuid.UUID | str) -> str:
    return f"{ADMIN_DRIVERS_URL}/{driver_id}"


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def as_admin(client: httpx.AsyncClient) -> dict[str, str]:
    return (await login_as(client, "admin")).csrf_headers


async def test_new_vehicle_is_economy(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())

    profile = (await client.get(DRIVERS_ME_URL)).json()

    assert profile["id"] == str(driver.id)
    assert profile["vehicle"]["car_class"] == "economy"


async def test_driver_cannot_set_the_class(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.patch(
        DRIVERS_ME_URL,
        json={"vehicle": vehicle(car_class="business")},
        headers=driver.csrf_headers,
    )

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


@pytest.mark.usefixtures("admin_id")
async def test_approval_sets_the_class(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    headers = await as_admin(client)

    response = await client.post(
        approve_url(driver.id), json={"car_class": "comfort"}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["vehicle"]["car_class"] == "comfort"
    [listed] = (await client.get(ADMIN_DRIVERS_URL)).json()["items"]
    assert listed["vehicle"]["car_class"] == "comfort"
    await login_as(client, "dana")
    assert (await client.get(DRIVERS_ME_URL)).json()["vehicle"]["car_class"] == "comfort"


@pytest.mark.usefixtures("admin_id")
@pytest.mark.parametrize("body", [None, {}])
async def test_approval_without_a_class_keeps_it(
    client: httpx.AsyncClient, body: dict[str, Any] | None
) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    headers = await as_admin(client)

    response = await client.post(approve_url(driver.id), json=body, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["vehicle"]["car_class"] == "economy"


@pytest.mark.usefixtures("admin_id")
@pytest.mark.parametrize("body", [{"car_class": "premium"}, {"car_class": None}, {"online": True}])
async def test_approval_rejects_an_invalid_body(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    headers = await as_admin(client)

    response = await client.post(approve_url(driver.id), json=body, headers=headers)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


@pytest.mark.usefixtures("admin_id")
async def test_admin_changes_the_class_of_an_approved_driver(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    driver_id = await driver_factory.driver("dana", location=NEAR_PICKUP)
    headers = await as_admin(client)

    response = await client.patch(
        driver_url(driver_id), json={"car_class": "business"}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["approval_status"], body["online"]) == ("approved", True)
    assert body["vehicle"]["car_class"] == "business"
    assert body["username"] == "dana"


@pytest.mark.usefixtures("admin_id")
@pytest.mark.parametrize("body", [{}, {"car_class": "premium"}, {"car_class": None}])
async def test_class_change_needs_a_valid_class(
    client: httpx.AsyncClient, driver_factory: DriverFactory, body: dict[str, Any]
) -> None:
    driver_id = await driver_factory.driver("dana")
    headers = await as_admin(client)

    response = await client.patch(driver_url(driver_id), json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.usefixtures("admin_id")
async def test_class_change_of_an_unknown_driver_is_not_found(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    headers = await as_admin(client)

    for target in (uuid.uuid4(), passenger.id):
        response = await client.patch(
            driver_url(target), json={"car_class": "comfort"}, headers=headers
        )
        assert response.status_code == 404
        assert error_code(response) == "driver_not_found"


@pytest.mark.usefixtures("admin_id")
async def test_class_change_needs_a_vehicle(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana", profile={"full_name": "Dana Driver"})
    headers = await as_admin(client)

    response = await client.patch(
        driver_url(driver.id), json={"car_class": "comfort"}, headers=headers
    )

    assert response.status_code == 409
    assert error_code(response) == "driver_profile_incomplete"
    assert response.json()["error"]["details"] == {"missing_fields": ["vehicle"]}


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_only_an_admin_changes_the_class(
    client: httpx.AsyncClient, driver_factory: DriverFactory, role: str
) -> None:
    driver_id = await driver_factory.driver("dana")
    user = await register_and_login(client, "mallory", role=role)

    response = await client.patch(
        driver_url(driver_id), json={"car_class": "business"}, headers=user.csrf_headers
    )

    assert response.status_code == 403


@pytest.mark.usefixtures("admin_id")
async def test_lowering_the_class_revokes_offers_above_it(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    driver_id = await driver_factory.driver("dana", location=NEAR_PICKUP, car_class=Tariff.BUSINESS)
    passenger = await register_and_login(client, "pat")
    ride = await order_ride(client, passenger, tariff="comfort")
    [offer] = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert offer.driver_id == driver_id
    headers = await as_admin(client)

    kept = await client.patch(driver_url(driver_id), json={"car_class": "comfort"}, headers=headers)
    [still_pending] = await dispatcher.offers(uuid.UUID(ride["id"]))
    lowered = await client.patch(
        driver_url(driver_id), json={"car_class": "economy"}, headers=headers
    )

    assert (kept.status_code, lowered.status_code) == (200, 200)
    assert still_pending.status is OfferStatus.PENDING
    [revoked] = await dispatcher.offers(uuid.UUID(ride["id"]))
    assert revoked.status is OfferStatus.REVOKED
