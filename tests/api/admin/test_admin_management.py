import uuid

import httpx
import pytest
from fastapi import FastAPI

from support.auth import PASSWORD, register_and_login
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.history import get_page, past_rides
from support.rides import PICKUP, RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.states import OfferStatus
from taxi_service.modules.users.models import UserProfile


async def test_search_is_unicode_aware_and_counts_filtered_rows(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    session_factory: SessionFactory,
) -> None:
    await driver_factory.admin_id()
    target = await ride_factory.passenger("target_user")
    await ride_factory.passenger("another_user")
    async with session_factory.begin() as db:
        db.add(
            UserProfile(
                user_id=target, display_name="Айгерим Садыкова", updated_at=ride_factory.clock.now()
            )
        )
    await login_as(client, "admin")
    body = await get_page(client, "/api/v1/admin/users", q="АЙГЕРИМ", limit=1)
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(target)
    assert (await get_page(client, "/api/v1/admin/users", q="%"))["total"] == 0


async def test_driver_card_is_loaded_directly_and_searches_plates(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
) -> None:
    driver_id = await driver_factory.driver("target_driver")
    await login_as(client, "admin")
    card = await client.get(f"/api/v1/admin/drivers/{driver_id}")
    assert card.status_code == 200
    assert card.json()["id"] == str(driver_id)
    body = await get_page(client, "/api/v1/admin/drivers", q="001tst", online=True)
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(driver_id)


async def test_admin_can_block_revoke_sessions_and_restore_access(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    app: FastAPI,
) -> None:
    await driver_factory.admin_id()
    passenger = await register_and_login(client, "blocked_passenger")
    passenger_cookies = dict(client.cookies)
    admin = await login_as(client, "admin")
    url = f"/api/v1/admin/users/{passenger.id}/access"
    response = await client.put(
        url, json={"blocked": True, "reason": "Проверка жалобы"}, headers=admin.csrf_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["block_reason"] == "Проверка жалобы"
    assert response.json()["blocked_at"] is not None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=client.base_url, cookies=passenger_cookies
    ) as other:
        assert (await other.get("/api/v1/auth/session")).status_code == 401
        denied = await other.post(
            "/api/v1/auth/login", json={"username": "blocked_passenger", "password": PASSWORD}
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "account_blocked"
    response = await client.put(url, json={"blocked": False}, headers=admin.csrf_headers)
    assert response.status_code == 200
    assert response.json()["blocked_at"] is None
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "blocked_passenger", "password": PASSWORD}
        )
    ).status_code == 200


async def test_blocking_protects_admin_and_active_ride(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
) -> None:
    admin_id = await driver_factory.admin_id()
    passenger = await ride_factory.passenger("riding_passenger")
    await ride_factory.searching_ride(passenger)
    admin = await login_as(client, "admin")
    for target, code in [
        (admin_id, "admin_account_protected"),
        (passenger, "account_has_active_ride"),
    ]:
        response = await client.put(
            f"/api/v1/admin/users/{target}/access",
            json={"blocked": True, "reason": "Проверка"},
            headers=admin.csrf_headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == code


async def test_rides_search_and_names_are_not_limited_to_loaded_people(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
) -> None:
    await driver_factory.admin_id()
    passenger = await ride_factory.passenger("find_passenger")
    await past_rides(ride_factory, passenger, 2)
    await past_rides(ride_factory, await ride_factory.passenger("other_passenger"), 1)
    await login_as(client, "admin")
    body = await get_page(client, "/api/v1/admin/rides", q="FIND_PASSENGER", limit=1, offset=1)
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["passenger_name"] == "find_passenger"


async def test_overview_counts_all_records(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
) -> None:
    await driver_factory.driver("online_driver")
    await driver_factory.driver("pending_driver", approved=False)
    await ride_factory.searching_ride()
    await login_as(client, "admin")
    response = await client.get("/api/v1/admin/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["pending_drivers"] == 1
    assert body["online_drivers"] == 1
    assert body["active_rides"] == 1
    assert body["total_users"] >= 4


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_management_routes_are_admin_only(client: httpx.AsyncClient, role: str) -> None:
    user = await register_and_login(client, f"test_{role}", role=role)
    assert (await client.get("/api/v1/admin/overview")).status_code == 403
    assert (await client.get(f"/api/v1/admin/drivers/{uuid.uuid4()}")).status_code == 403
    assert (
        await client.put(
            f"/api/v1/admin/users/{user.id}/access",
            json={"blocked": True, "reason": "test"},
            headers=user.csrf_headers,
        )
    ).status_code == 403


async def test_blocking_driver_revokes_offer_and_takes_them_offline(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
) -> None:
    driver_id = await driver_factory.driver("block_driver", location=PICKUP)
    ride = await ride_factory.searching_ride()
    await dispatcher.process(ride.id)
    assert (await dispatcher.offers(ride.id))[0].status is OfferStatus.PENDING
    admin = await login_as(client, "admin")
    response = await client.put(
        f"/api/v1/admin/users/{driver_id}/access",
        json={"blocked": True, "reason": "Проверка жалобы"},
        headers=admin.csrf_headers,
    )
    assert response.status_code == 200
    card = (await client.get(f"/api/v1/admin/drivers/{driver_id}")).json()
    assert card["online"] is False
    assert card["blocked_at"] is not None
    assert (await dispatcher.offers(ride.id))[0].status is OfferStatus.REVOKED


async def test_access_update_requires_csrf_and_block_reason(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
) -> None:
    await driver_factory.admin_id()
    passenger_id = await ride_factory.passenger()
    admin = await login_as(client, "admin")
    url = f"/api/v1/admin/users/{passenger_id}/access"
    no_csrf = await client.put(url, json={"blocked": True, "reason": "test"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "csrf_failed"
    no_reason = await client.put(url, json={"blocked": True}, headers=admin.csrf_headers)
    assert no_reason.status_code == 422
    account = (await client.get(f"/api/v1/admin/users/{passenger_id}")).json()
    assert account["blocked_at"] is None
