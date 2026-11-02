"""GET /admin/drivers and POST /admin/drivers/{id}/approve: admin only."""

import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.auth import register_and_login
from support.clock import ManualClock
from support.drivers import (
    ADMIN_DRIVERS_URL,
    approve,
    approve_url,
    complete_profile,
    create_admin,
    login_as,
    registered_driver,
)
from taxi_service.database.session import SessionFactory


@pytest.fixture
async def admin_id(app: FastAPI, session_factory: SessionFactory, clock: ManualClock) -> uuid.UUID:
    return await create_admin(app, session_factory, clock)


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


# Access ----------------------------------------------------------------------


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_other_roles_cannot_list_or_approve(client: httpx.AsyncClient, role: str) -> None:
    target = await registered_driver(client, "target", profile=complete_profile())
    user = await register_and_login(client, "mallory", role=role)

    listing = await client.get(ADMIN_DRIVERS_URL)
    approval = await client.post(approve_url(target.id), headers=user.csrf_headers)
    self_approval = await client.post(approve_url(user.id), headers=user.csrf_headers)

    assert [listing.status_code, approval.status_code, self_approval.status_code] == [403] * 3
    assert error_code(approval) == "forbidden"


async def test_admin_routes_need_a_session(client: httpx.AsyncClient) -> None:
    assert (await client.get(ADMIN_DRIVERS_URL)).status_code == 401
    assert (await client.post(approve_url(uuid.uuid4()))).status_code == 401


async def test_approve_needs_the_csrf_token(client: httpx.AsyncClient, admin_id: uuid.UUID) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    await login_as(client, "admin")

    response = await client.post(approve_url(driver.id))

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


# Approval --------------------------------------------------------------------


async def test_admin_approves_a_complete_driver(
    client: httpx.AsyncClient, clock: ManualClock, admin_id: uuid.UUID
) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    clock.advance(timedelta(minutes=5))

    response = await approve(client, driver.id)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(driver.id)
    assert body["username"] == "dana"
    assert body["approval_status"] == "approved"
    assert body["approved_at"] == "2026-11-03T09:05:00Z"
    assert body["approved_by"] == str(admin_id)
    assert body["online"] is False
    assert body["vehicle"]["plate_number"] == "123ABC02"
    dana = await login_as(client, "dana")
    assert dana.id == driver.id


async def test_repeated_approval_returns_the_first_approval(
    client: httpx.AsyncClient, clock: ManualClock, admin_id: uuid.UUID
) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile())
    first = await approve(client, driver.id)
    clock.advance(timedelta(minutes=1))

    second = await approve(client, driver.id)

    assert second.status_code == 200
    assert second.json() == first.json()


@pytest.mark.parametrize(
    ("profile", "missing"),
    [
        (None, ["full_name", "phone", "license_number", "vehicle"]),
        (
            {"full_name": "Dana", "phone": "+77011234567", "license_number": "KZ1234567"},
            ["vehicle"],
        ),
        (
            {"full_name": "Dana", "vehicle": complete_profile()["vehicle"]},
            ["phone", "license_number"],
        ),
    ],
)
async def test_incomplete_driver_is_not_approved(
    client: httpx.AsyncClient,
    admin_id: uuid.UUID,
    profile: dict[str, Any] | None,
    missing: list[str],
) -> None:
    driver = await registered_driver(client, "dana", profile=profile)

    response = await approve(client, driver.id)

    assert response.status_code == 409
    assert error_code(response) == "driver_profile_incomplete"
    assert response.json()["error"]["details"] == {"missing_fields": missing}
    listed = (await client.get(ADMIN_DRIVERS_URL)).json()["items"]
    assert [item["approval_status"] for item in listed] == ["pending"]


async def test_unknown_id_or_non_driver_is_not_found(
    client: httpx.AsyncClient, admin_id: uuid.UUID
) -> None:
    passenger = await register_and_login(client, "pat")
    admin = await login_as(client, "admin")

    for target in (uuid.uuid4(), passenger.id, admin_id):
        response = await client.post(approve_url(target), headers=admin.csrf_headers)
        assert response.status_code == 404
        assert error_code(response) == "driver_not_found"
    malformed = await client.post(approve_url("not-a-uuid"), headers=admin.csrf_headers)
    assert malformed.status_code == 422


# Listing ---------------------------------------------------------------------


async def three_drivers(client: httpx.AsyncClient, clock: ManualClock) -> list[str]:
    """Registered a minute apart (oldest first); a passenger is never listed."""
    ids = []
    for index, name in enumerate(["first", "second", "third"]):
        driver = await registered_driver(client, name, profile=complete_profile(f"{index}00AAA02"))
        ids.append(str(driver.id))
        clock.advance(timedelta(minutes=1))
    await register_and_login(client, "passenger")
    return ids


async def test_list_is_newest_first_with_default_page(
    client: httpx.AsyncClient, clock: ManualClock, admin_id: uuid.UUID
) -> None:
    first, second, third = await three_drivers(client, clock)
    await login_as(client, "admin")

    response = await client.get(ADMIN_DRIVERS_URL)

    assert response.status_code == 200
    page = response.json()
    assert (page["limit"], page["offset"], page["total"]) == (20, 0, 3)
    assert [item["id"] for item in page["items"]] == [third, second, first]
    item = page["items"][0]
    assert item["username"] == "third"
    assert item["created_at"] == "2026-11-03T09:02:00Z"
    assert item["missing_fields"] == []
    assert (item["approval_status"], item["approved_by"], item["online"]) == (
        "pending",
        None,
        False,
    )


async def test_list_pages_with_limit_and_offset(
    client: httpx.AsyncClient, clock: ManualClock, admin_id: uuid.UUID
) -> None:
    first, second, third = await three_drivers(client, clock)
    await login_as(client, "admin")

    head = (await client.get(ADMIN_DRIVERS_URL, params={"limit": 2})).json()
    tail = (await client.get(ADMIN_DRIVERS_URL, params={"limit": 2, "offset": 2})).json()
    beyond = (await client.get(ADMIN_DRIVERS_URL, params={"offset": 10})).json()

    assert [item["id"] for item in head["items"]] == [third, second]
    assert [item["id"] for item in tail["items"]] == [first]
    assert (tail["limit"], tail["offset"], tail["total"]) == (2, 2, 3)
    assert (beyond["items"], beyond["total"]) == ([], 3)


async def test_same_registration_time_is_ordered_by_id_descending(
    client: httpx.AsyncClient, admin_id: uuid.UUID
) -> None:
    ids = [str((await registered_driver(client, f"driver_{index}")).id) for index in range(4)]
    await login_as(client, "admin")

    page = (await client.get(ADMIN_DRIVERS_URL)).json()

    assert [item["id"] for item in page["items"]] == sorted(ids, reverse=True)


async def test_list_filters_by_approval_status(
    client: httpx.AsyncClient, clock: ManualClock, admin_id: uuid.UUID
) -> None:
    first, second, third = await three_drivers(client, clock)
    await approve(client, uuid.UUID(second))

    approved = (await client.get(ADMIN_DRIVERS_URL, params={"approval_status": "approved"})).json()
    pending = (await client.get(ADMIN_DRIVERS_URL, params={"approval_status": "pending"})).json()

    assert ([item["id"] for item in approved["items"]], approved["total"]) == ([second], 1)
    assert ([item["id"] for item in pending["items"]], pending["total"]) == ([third, first], 2)


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"approval_status": "banned"}, {"limit": "x"}],
)
async def test_invalid_list_parameters_are_rejected(
    client: httpx.AsyncClient, admin_id: uuid.UUID, params: dict[str, Any]
) -> None:
    await login_as(client, "admin")

    response = await client.get(ADMIN_DRIVERS_URL, params=params)

    assert response.status_code == 422


async def test_limit_of_one_hundred_is_allowed(
    client: httpx.AsyncClient, admin_id: uuid.UUID
) -> None:
    await login_as(client, "admin")

    response = await client.get(ADMIN_DRIVERS_URL, params={"limit": 100})

    assert (response.status_code, response.json()["limit"]) == (200, 100)
