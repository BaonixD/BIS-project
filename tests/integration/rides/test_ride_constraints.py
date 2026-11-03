"""Database constraints of ride_quotes, rides and idempotency_records, without Python checks.

Rows are inserted with raw SQL, so only the schema can reject them: one active ride
per passenger, one accepted active ride per driver, one ride per quote, a driver
that matches the status, and one idempotency record per user, operation and key.
"""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import SessionFactory

NOW = "2026-11-03 09:00:00.000000"
LATER = "2026-11-03 09:05:00.000000"
GEOMETRY = json.dumps({"type": "LineString", "coordinates": [[76.95, 43.23], [76.92, 43.21]]})


async def insert(session_factory: SessionFactory, table: str, row: dict[str, Any]) -> None:
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    async with session_factory.begin() as session:
        await session.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({params})"), row)


async def insert_user(session_factory: SessionFactory, role: str = "passenger") -> str:
    user_id = uuid.uuid4().hex
    await insert(
        session_factory,
        "users",
        {
            "id": user_id,
            "username": f"u{user_id[:8]}",
            "username_normalized": f"u{user_id[:8]}",
            "password_hash": "hash",
            "role": role,
            "created_at": NOW,
        },
    )
    return user_id


async def insert_driver(session_factory: SessionFactory) -> str:
    driver_id = await insert_user(session_factory, role="driver")
    await insert(
        session_factory,
        "driver_profiles",
        {
            "user_id": driver_id,
            "approval_status": "pending",
            "is_online": False,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    return driver_id


def route_snapshot(**values: Any) -> dict[str, Any]:
    return {
        "pickup_longitude": 76.9572,
        "pickup_latitude": 43.2389,
        "dropoff_longitude": 76.9286,
        "dropoff_latitude": 43.2187,
        "distance_m": 10_000,
        "duration_s": 1_500,
        "route_geometry": GEOMETRY,
        "provider": "fake",
        "currency": "KZT",
        "tariff_version": "edu-v2",
        **values,
    }


QUOTE_AMOUNTS = {
    "economy_amount_kzt": 2200,
    "comfort_amount_kzt": 2925,
    "comfort_plus_amount_kzt": 3650,
    "business_amount_kzt": 4800,
}


async def insert_quote(
    session_factory: SessionFactory, passenger_id: str | None = None, **values: Any
) -> str:
    quote_id = uuid.uuid4().hex
    row = {
        "id": quote_id,
        "passenger_id": passenger_id or await insert_user(session_factory),
        **route_snapshot(),
        **QUOTE_AMOUNTS,
        "created_at": NOW,
        "expires_at": LATER,
        **values,
    }
    await insert(session_factory, "ride_quotes", row)
    return quote_id


async def insert_ride(
    session_factory: SessionFactory,
    passenger_id: str | None = None,
    *,
    status: str = "searching",
    driver_id: str | None = None,
    **values: Any,
) -> str:
    passenger_id = passenger_id or await insert_user(session_factory)
    quote_id = values.pop("quote_id", None) or await insert_quote(session_factory, passenger_id)
    ride_id = uuid.uuid4().hex
    row = {
        "id": ride_id,
        "passenger_id": passenger_id,
        "driver_id": driver_id,
        "quote_id": quote_id,
        "status": status,
        **route_snapshot(),
        "amount_kzt": 2200,
        "created_at": NOW,
        "updated_at": NOW,
        "search_started_at": NOW,
        "search_deadline": LATER,
        **values,
    }
    await insert(session_factory, "rides", row)
    return ride_id


async def insert_idempotency_record(
    session_factory: SessionFactory, user_id: str, key: str = "key-1", **values: Any
) -> None:
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "operation": "create_ride",
        "key": key,
        "request_fingerprint": "a" * 64,
        "resource_id": uuid.uuid4().hex,
        "created_at": NOW,
        **values,
    }
    await insert(session_factory, "idempotency_records", row)


# ride_quotes


async def test_valid_quote_is_stored(session_factory: SessionFactory) -> None:
    await insert_quote(
        session_factory,
        pickup_longitude=-180,
        pickup_latitude=90,
        dropoff_longitude=180,
        dropoff_latitude=-90,
        distance_m=0,
        duration_s=0,
    )


@pytest.mark.parametrize(
    "values",
    [
        {"pickup_longitude": 180.000001},
        {"pickup_latitude": -90.000001},
        {"dropoff_longitude": -180.000001},
        {"dropoff_latitude": 90.000001},
        {"distance_m": -1},
        {"duration_s": -1},
        {"economy_amount_kzt": 0},
        {"comfort_amount_kzt": -2925},
        {"comfort_plus_amount_kzt": 0},
        {"business_amount_kzt": 0},
        {"currency": "USD"},
        {"expires_at": NOW},
    ],
)
async def test_quote_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_quote(session_factory, **values)


async def test_quote_belongs_to_an_existing_user(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_quote(session_factory, passenger_id=uuid.uuid4().hex)


# rides: values and references


@pytest.mark.parametrize(
    "values",
    [
        {"status": "lost"},
        {"pickup_latitude": 90.5},
        {"dropoff_longitude": 181},
        {"distance_m": -1},
        {"duration_s": -1},
        {"amount_kzt": 0},
        {"currency": "EUR"},
        {"tariff": "premium"},
    ],
)
async def test_ride_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_ride(session_factory, **values)


async def test_ride_tariff_defaults_to_economy(session_factory: SessionFactory) -> None:
    ride_id = await insert_ride(session_factory)

    async with session_factory.begin() as session:
        tariff = await session.scalar(
            text("SELECT tariff FROM rides WHERE id = :id"), {"id": ride_id}
        )

    assert tariff == "economy"


async def test_ride_needs_an_existing_quote(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_ride(session_factory, quote_id=uuid.uuid4().hex)


async def test_ride_needs_an_existing_passenger(session_factory: SessionFactory) -> None:
    quote = await insert_quote(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_ride(session_factory, uuid.uuid4().hex, quote_id=quote)


async def test_assigned_driver_must_have_a_driver_profile(session_factory: SessionFactory) -> None:
    passenger_as_driver = await insert_user(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_ride(session_factory, status="assigned", driver_id=passenger_as_driver)


async def test_one_ride_per_quote(session_factory: SessionFactory) -> None:
    passenger = await insert_user(session_factory)
    quote = await insert_quote(session_factory, passenger)
    await insert_ride(session_factory, passenger, status="cancelled", quote_id=quote)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_ride(session_factory, passenger, quote_id=quote)


# rides: driver matches the status


@pytest.mark.parametrize("status", ["searching", "no_driver", "cancelled"])
async def test_ride_without_driver_in_unassigned_statuses(
    session_factory: SessionFactory, status: str
) -> None:
    await insert_ride(session_factory, status=status)


@pytest.mark.parametrize("status", ["assigned", "arrived", "in_progress", "completed", "cancelled"])
async def test_ride_with_driver_in_assigned_statuses(
    session_factory: SessionFactory, status: str
) -> None:
    await insert_ride(
        session_factory, status=status, driver_id=await insert_driver(session_factory)
    )


@pytest.mark.parametrize("status", ["assigned", "arrived", "in_progress", "completed"])
async def test_assigned_statuses_need_a_driver(
    session_factory: SessionFactory, status: str
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_ride(session_factory, status=status)


@pytest.mark.parametrize("status", ["searching", "no_driver"])
async def test_unassigned_statuses_have_no_driver(
    session_factory: SessionFactory, status: str
) -> None:
    driver = await insert_driver(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_ride(session_factory, status=status, driver_id=driver)


# rides: active-ride limits (partial unique indexes)


@pytest.mark.parametrize("second", ["searching", "assigned", "arrived", "in_progress"])
async def test_one_active_ride_per_passenger(session_factory: SessionFactory, second: str) -> None:
    passenger = await insert_user(session_factory)
    await insert_ride(session_factory, passenger, status="searching")
    driver = None if second == "searching" else await insert_driver(session_factory)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_ride(session_factory, passenger, status=second, driver_id=driver)


async def test_finished_rides_do_not_block_a_new_one(session_factory: SessionFactory) -> None:
    passenger = await insert_user(session_factory)
    driver = await insert_driver(session_factory)
    await insert_ride(session_factory, passenger, status="completed", driver_id=driver)
    await insert_ride(session_factory, passenger, status="cancelled")
    await insert_ride(session_factory, passenger, status="no_driver")

    await insert_ride(session_factory, passenger, status="searching")


async def test_other_passengers_have_their_own_active_ride(
    session_factory: SessionFactory,
) -> None:
    await insert_ride(session_factory, status="searching")
    await insert_ride(session_factory, status="searching")


@pytest.mark.parametrize("second", ["assigned", "arrived", "in_progress"])
async def test_one_accepted_active_ride_per_driver(
    session_factory: SessionFactory, second: str
) -> None:
    driver = await insert_driver(session_factory)
    await insert_ride(session_factory, status="arrived", driver_id=driver)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_ride(session_factory, status=second, driver_id=driver)


async def test_driver_history_does_not_block_a_new_assignment(
    session_factory: SessionFactory,
) -> None:
    driver = await insert_driver(session_factory)
    await insert_ride(session_factory, status="completed", driver_id=driver)
    await insert_ride(session_factory, status="cancelled", driver_id=driver)

    await insert_ride(session_factory, status="assigned", driver_id=driver)


# idempotency_records


async def test_idempotency_key_is_unique_per_user_and_operation(
    session_factory: SessionFactory,
) -> None:
    user = await insert_user(session_factory)
    other = await insert_user(session_factory)
    await insert_idempotency_record(session_factory, user)
    await insert_idempotency_record(session_factory, other)
    await insert_idempotency_record(session_factory, user, operation="other_operation")

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_idempotency_record(session_factory, user)


@pytest.mark.parametrize(
    "values", [{"key": ""}, {"key": "k" * 129}, {"request_fingerprint": "abc"}]
)
async def test_idempotency_record_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    user = await insert_user(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_idempotency_record(session_factory, user, **values)


async def test_idempotency_record_belongs_to_an_existing_user(
    session_factory: SessionFactory,
) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_idempotency_record(session_factory, uuid.uuid4().hex)
