"""Rows inserted with raw SQL, so that only the schema can accept or reject them.

Usage in a constraint test with the ``session_factory`` fixture::

    driver = await insert_driver(session_factory)
    ride = await insert_ride(session_factory)
    await insert_offer(session_factory, ride, driver)            # pending
    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_offer(session_factory, ride, await insert_driver(session_factory))

Times are SQLite text in UTC, as ``UtcDateTime`` stores them.
"""

import json
import uuid
from typing import Any

from sqlalchemy import text

from taxi_service.database.session import SessionFactory

NOW = "2026-11-03 09:00:00.000000"
IN_30_S = "2026-11-03 09:00:30.000000"
IN_3_MIN = "2026-11-03 09:03:00.000000"
IN_5_MIN = "2026-11-03 09:05:00.000000"
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


def route_snapshot() -> dict[str, Any]:
    return {
        "pickup_longitude": 76.9572,
        "pickup_latitude": 43.2389,
        "dropoff_longitude": 76.9286,
        "dropoff_latitude": 43.2187,
        "distance_m": 10_000,
        "duration_s": 1_500,
        "route_geometry": GEOMETRY,
        "provider": "fake",
        "amount_kzt": 2200,
        "currency": "KZT",
        "tariff_version": "edu-v1",
    }


async def insert_quote(session_factory: SessionFactory, passenger_id: str) -> str:
    quote_id = uuid.uuid4().hex
    row = {
        "id": quote_id,
        "passenger_id": passenger_id,
        **route_snapshot(),
        "created_at": NOW,
        "expires_at": IN_5_MIN,
    }
    await insert(session_factory, "ride_quotes", row)
    return quote_id


async def insert_ride(
    session_factory: SessionFactory,
    *,
    status: str = "searching",
    driver_id: str | None = None,
    **values: Any,
) -> str:
    passenger_id = await insert_user(session_factory)
    ride_id = uuid.uuid4().hex
    row = {
        "id": ride_id,
        "passenger_id": passenger_id,
        "driver_id": driver_id,
        "quote_id": await insert_quote(session_factory, passenger_id),
        "status": status,
        **route_snapshot(),
        "created_at": NOW,
        "updated_at": NOW,
        "search_started_at": NOW,
        "search_deadline": IN_3_MIN,
        **values,
    }
    await insert(session_factory, "rides", row)
    return ride_id


async def insert_offer(
    session_factory: SessionFactory,
    ride_id: str,
    driver_id: str,
    *,
    status: str = "pending",
    **values: Any,
) -> str:
    offer_id = uuid.uuid4().hex
    row = {
        "id": offer_id,
        "ride_id": ride_id,
        "driver_id": driver_id,
        "status": status,
        "created_at": NOW,
        "expires_at": IN_30_S,
        "responded_at": None if status == "pending" else IN_30_S,
        **values,
    }
    await insert(session_factory, "ride_offers", row)
    return offer_id
