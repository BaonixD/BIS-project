"""GET /api/v1/rides/{id}: the passenger, the assigned driver and admins; others get 404."""

import uuid
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import update

from support.auth import register_and_login
from support.clock import ManualClock
from support.drivers import DriverFactory, create_admin, login_as
from support.rides import order_ride, ride_url
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus


def error_of(response: httpx.Response) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return error


async def assign(
    session_factory: SessionFactory, ride_id: str, driver_id: uuid.UUID | None, status: RideStatus
) -> None:
    """Stand-in for dispatch (T06): set the driver and status directly."""
    async with session_factory.begin() as session:
        await session.execute(
            update(Ride)
            .where(Ride.id == uuid.UUID(ride_id))
            .values(driver_id=driver_id, status=status)
        )


async def test_passenger_reads_their_ride(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 200
    assert response.json() == created


async def test_new_ride_has_no_driver_yet(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)

    body = (await client.get(ride_url(created["id"]))).json()

    assert (body["status"], body["driver_id"]) == ("searching", None)


async def test_another_passenger_gets_not_found(client: httpx.AsyncClient) -> None:
    owner = await register_and_login(client, "owner")
    created = await order_ride(client, owner)
    await register_and_login(client, "stranger")

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 404
    assert error_of(response) == {
        "code": "ride_not_found",
        "message": "Ride not found.",
        "details": {},
    }


async def test_unassigned_driver_gets_not_found(
    client: httpx.AsyncClient, driver_factory: DriverFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)
    await driver_factory.driver("dana")
    await login_as(client, "dana")

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 404
    assert error_of(response)["code"] == "ride_not_found"


async def test_assigned_driver_reads_the_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory, driver_factory: DriverFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)
    driver_id = await driver_factory.driver("dana")
    await assign(session_factory, created["id"], driver_id, RideStatus.ASSIGNED)
    await login_as(client, "dana")

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["driver_id"]) == (
        "assigned",
        str(driver_id),
    )


async def test_driver_loses_access_after_release(
    client: httpx.AsyncClient, session_factory: SessionFactory, driver_factory: DriverFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)
    driver_id = await driver_factory.driver("dana")
    await assign(session_factory, created["id"], driver_id, RideStatus.ASSIGNED)
    await assign(session_factory, created["id"], None, RideStatus.SEARCHING)
    await login_as(client, "dana")

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 404


async def test_admin_reads_any_ride(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)
    await create_admin(app, session_factory, clock)
    await login_as(client, "admin")

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 200
    assert response.json() == created


async def test_unknown_ride_is_not_found(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "pat")

    response = await client.get(ride_url(uuid.uuid4()))

    assert response.status_code == 404
    assert error_of(response)["code"] == "ride_not_found"


async def test_malformed_ride_id_is_a_validation_error(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "pat")

    response = await client.get(ride_url("not-a-uuid"))

    assert response.status_code == 422
    assert error_of(response)["code"] == "validation_error"


async def test_reading_a_ride_needs_a_session(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    created = await order_ride(client, passenger)
    client.cookies.clear()

    response = await client.get(ride_url(created["id"]))

    assert response.status_code == 401
    assert error_of(response)["code"] == "not_authenticated"
