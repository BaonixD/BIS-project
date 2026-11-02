"""GET/PATCH /drivers/me: the driver's own profile and single vehicle."""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from support.auth import register_and_login
from support.clock import ManualClock
from support.drivers import (
    AVAILABILITY_URL,
    DRIVERS_ME_URL,
    LOCATION_URL,
    approve,
    complete_profile,
    create_admin,
    login_as,
    registered_driver,
    vehicle,
)
from taxi_service.database.session import SessionFactory

ALL_MISSING = ["full_name", "phone", "license_number", "vehicle"]


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_new_driver_has_an_empty_pending_profile(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.get(DRIVERS_ME_URL)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(driver.id),
        "full_name": None,
        "phone": None,
        "license_number": None,
        "vehicle": None,
        "approval_status": "pending",
        "approved_at": None,
        "online": False,
        "location": None,
        "location_updated_at": None,
        "missing_fields": ALL_MISSING,
    }


async def test_complete_profile_is_normalized_and_stored(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana")
    body = {
        "full_name": "  Dana Driver ",
        "phone": "+7 (701) 123-45-67",
        "license_number": "kz 123 4567",
        "vehicle": vehicle("123 abc-02", make=" Toyota "),
    }

    response = await client.patch(DRIVERS_ME_URL, json=body, headers=driver.csrf_headers)

    assert response.status_code == 200
    profile = response.json()
    assert (profile["full_name"], profile["phone"], profile["license_number"]) == (
        "Dana Driver",
        "+77011234567",
        "KZ1234567",
    )
    assert profile["vehicle"] == {
        "make": "Toyota",
        "model": "Camry",
        "color": "white",
        "plate_number": "123ABC02",
        "year": 2020,
    }
    assert profile["missing_fields"] == []
    assert profile["approval_status"] == "pending"
    assert (await client.get(DRIVERS_ME_URL)).json() == profile


async def test_partial_updates_keep_other_fields(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana")

    await client.patch(DRIVERS_ME_URL, json={"full_name": "Dana"}, headers=driver.csrf_headers)
    response = await client.patch(
        DRIVERS_ME_URL, json={"vehicle": vehicle()}, headers=driver.csrf_headers
    )

    assert response.json()["full_name"] == "Dana"
    assert response.json()["vehicle"]["plate_number"] == "123ABC02"
    assert response.json()["missing_fields"] == ["phone", "license_number"]


async def test_vehicle_is_replaced_not_duplicated(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile("111AAA02"))

    response = await client.patch(
        DRIVERS_ME_URL,
        json={"vehicle": vehicle("222BBB02", color="black")},
        headers=driver.csrf_headers,
    )

    assert response.status_code == 200
    assert response.json()["vehicle"]["plate_number"] == "222BBB02"
    assert response.json()["vehicle"]["color"] == "black"


async def test_plate_number_of_another_driver_is_rejected(client: httpx.AsyncClient) -> None:
    await registered_driver(client, "dana", profile=complete_profile("123ABC02"))
    other = await registered_driver(client, "omar")

    response = await client.patch(
        DRIVERS_ME_URL, json={"vehicle": vehicle("123 abc 02")}, headers=other.csrf_headers
    )

    assert response.status_code == 409
    assert error_code(response) == "plate_number_taken"
    assert (await client.get(DRIVERS_ME_URL)).json()["vehicle"] is None


async def test_own_plate_number_can_be_sent_again(client: httpx.AsyncClient) -> None:
    driver = await registered_driver(client, "dana", profile=complete_profile("123ABC02"))

    response = await client.patch(
        DRIVERS_ME_URL,
        json={"vehicle": vehicle("123ABC02", color="red")},
        headers=driver.csrf_headers,
    )

    assert response.status_code == 200


@pytest.mark.parametrize("year", [1979, 2028])
async def test_vehicle_year_outside_reasonable_range_is_rejected(
    client: httpx.AsyncClient, year: int
) -> None:
    # The clock is at 2026: the newest accepted model year is 2027.
    driver = await registered_driver(client, "dana")

    response = await client.patch(
        DRIVERS_ME_URL, json={"vehicle": vehicle(year=year)}, headers=driver.csrf_headers
    )

    assert response.status_code == 422
    assert (await client.get(DRIVERS_ME_URL)).json()["vehicle"] is None


@pytest.mark.parametrize("year", [1980, 2027])
async def test_vehicle_year_bounds_are_inclusive(client: httpx.AsyncClient, year: int) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.patch(
        DRIVERS_ME_URL, json={"vehicle": vehicle(year=year)}, headers=driver.csrf_headers
    )

    assert response.status_code == 200
    assert response.json()["vehicle"]["year"] == year


@pytest.mark.parametrize(
    "body",
    [
        {"approval_status": "approved"},
        {"approved_at": "2026-11-03T09:00:00Z"},
        {"approved_by": "00000000-0000-0000-0000-000000000000"},
        {"online": True},
        {"location": {"longitude": 76.9, "latitude": 43.2}},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"role": "admin"},
        {"full_name": None},
        {"vehicle": None},
        {"full_name": " "},
        {"phone": "8701"},
        {"license_number": "A1"},
        {"vehicle": {"make": "Toyota"}},
        {"vehicle": vehicle(plate_number="!!")},
        {"vehicle": vehicle(year="2020")},
        {"vehicle": {**vehicle(), "owner_id": "x"}},
    ],
)
async def test_invalid_or_protected_fields_are_rejected(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    driver = await registered_driver(client, "dana")

    response = await client.patch(DRIVERS_ME_URL, json=body, headers=driver.csrf_headers)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    profile = (await client.get(DRIVERS_ME_URL)).json()
    assert profile["missing_fields"] == ALL_MISSING
    assert (profile["approval_status"], profile["online"]) == ("pending", False)


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("GET", DRIVERS_ME_URL, None),
        ("PATCH", DRIVERS_ME_URL, {"full_name": "Pat"}),
        ("PUT", AVAILABILITY_URL, {"online": True}),
        ("PUT", LOCATION_URL, {"longitude": 76.9, "latitude": 43.2}),
    ],
)
@pytest.mark.parametrize("role", ["passenger", "admin"])
async def test_driver_commands_are_forbidden_for_other_roles(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    role: str,
    method: str,
    url: str,
    body: dict[str, Any] | None,
) -> None:
    if role == "admin":
        await create_admin(app, session_factory, clock)
        user = await login_as(client, "admin")
    else:
        user = await register_and_login(client, "pat", role=role)

    response = await client.request(method, url, json=body, headers=user.csrf_headers)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


@pytest.mark.parametrize(
    ("method", "url"),
    [("GET", DRIVERS_ME_URL), ("PATCH", DRIVERS_ME_URL), ("PUT", AVAILABILITY_URL)],
)
async def test_driver_commands_need_a_session(
    client: httpx.AsyncClient, method: str, url: str
) -> None:
    response = await client.request(method, url, json={})

    assert response.status_code == 401


async def test_profile_update_needs_the_csrf_token(client: httpx.AsyncClient) -> None:
    await registered_driver(client, "dana")

    response = await client.patch(DRIVERS_ME_URL, json={"full_name": "Dana"})

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


async def test_profile_of_another_driver_is_not_reachable(client: httpx.AsyncClient) -> None:
    omar = await registered_driver(client, "omar", profile=complete_profile("111AAA02"))
    dana = await registered_driver(client, "dana")

    by_id = await client.get(f"/api/v1/drivers/{omar.id}")
    own = await client.patch(DRIVERS_ME_URL, json={"full_name": "Dana"}, headers=dana.csrf_headers)

    assert by_id.status_code == 404
    assert own.json()["id"] == str(dana.id)
    assert own.json()["vehicle"] is None


# Changes after approval ------------------------------------------------------


async def approved(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> dict[str, str]:
    await create_admin(app, session_factory, clock)
    driver = await registered_driver(client, "dana", profile=complete_profile())
    assert (await approve(client, driver.id)).status_code == 200
    driver = await login_as(client, "dana")
    online = await client.put(AVAILABILITY_URL, json={"online": True}, headers=driver.csrf_headers)
    assert online.json()["online"] is True
    return driver.csrf_headers


@pytest.mark.parametrize(
    "change",
    [
        {"full_name": "Someone Else"},
        {"license_number": "KZ7654321"},
        {"vehicle": vehicle("999ZZZ02")},
        {"vehicle": vehicle(color="black")},
    ],
)
async def test_identity_or_vehicle_change_returns_driver_to_pending_and_offline(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    change: dict[str, Any],
) -> None:
    headers = await approved(app, client, session_factory, clock)

    response = await client.patch(DRIVERS_ME_URL, json=change, headers=headers)

    assert response.status_code == 200
    profile = response.json()
    assert (profile["approval_status"], profile["approved_at"], profile["online"]) == (
        "pending",
        None,
        False,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"phone": "+77779998877"},
        {"full_name": "Dana Driver"},
        {"vehicle": vehicle("123 abc 02")},
    ],
)
async def test_phone_or_unchanged_values_keep_the_approval(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    change: dict[str, Any],
) -> None:
    headers = await approved(app, client, session_factory, clock)

    response = await client.patch(DRIVERS_ME_URL, json=change, headers=headers)

    assert response.status_code == 200
    assert (response.json()["approval_status"], response.json()["online"]) == ("approved", True)
