"""Finished rides for history and admin-list tests, and a counter of SQL statements.

A ride gets its driver and final status with a direct UPDATE: quicker than
dispatch and the ride commands (``support.lifecycle``) when only the list
matters. Usage with the ``ride_factory`` and ``session_factory`` fixtures::

    ids = await past_rides(ride_factory, passenger_id, 3)          # oldest first
    await set_ride(session_factory, ids[0], RideStatus.COMPLETED, driver_id)
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncEngine

from support.rides import RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus

ADMIN_RIDES_URL = "/api/v1/admin/rides"
ADMIN_USERS_URL = "/api/v1/admin/users"
STEP = timedelta(minutes=1)
RIDE_SUMMARY_FIELDS = frozenset(
    {
        "id",
        "status",
        "passenger_id",
        "driver_id",
        "pickup",
        "dropoff",
        "distance_m",
        "duration_s",
        "amount_kzt",
        "currency",
        "created_at",
        "updated_at",
        "payment_status",
        "payment_method",
    }
)


async def get_page(client: httpx.AsyncClient, url: str, **params: Any) -> dict[str, Any]:
    """GET a list that must answer 200; the JSON page."""
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def set_ride(
    session_factory: SessionFactory,
    ride_id: uuid.UUID,
    status: RideStatus,
    driver_id: uuid.UUID | None = None,
) -> None:
    """Stand-in for dispatch and the lifecycle: set the status and the driver directly."""
    async with session_factory.begin() as session:
        await session.execute(
            update(Ride).where(Ride.id == ride_id).values(status=status, driver_id=driver_id)
        )


async def past_rides(
    ride_factory: RideFactory,
    passenger_id: uuid.UUID,
    count: int,
    *,
    status: RideStatus = RideStatus.CANCELLED,
    driver_id: uuid.UUID | None = None,
    step: timedelta = STEP,
) -> list[uuid.UUID]:
    """``count`` finished rides of one passenger, oldest first.

    The test clock moves by ``step`` before each ride; ``step=timedelta(0)``
    gives them all the same ``created_at``.
    """
    ids = []
    for _ in range(count):
        if step:
            ride_factory.clock.advance(step)
        ride = await ride_factory.searching_ride(passenger_id)
        await set_ride(ride_factory.session_factory, ride.id, status, driver_id)
        ids.append(ride.id)
    return ids


def newest_first(ids: list[uuid.UUID]) -> list[str]:
    """Expected order of rides created one after another: the last one first."""
    return [str(ride_id) for ride_id in reversed(ids)]


def ids_of(body: dict[str, Any]) -> list[str]:
    return [item["id"] for item in body["items"]]


@dataclass
class StatementCounter:
    statements: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.statements)

    @property
    def queries(self) -> int:
        """Statements that read or write rows (not PRAGMA, BEGIN, COMMIT)."""
        verbs = ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH")
        return sum(statement.lstrip().upper().startswith(verbs) for statement in self.statements)


@contextmanager
def count_statements(engine: AsyncEngine) -> Iterator[StatementCounter]:
    """Every SQL statement ``engine`` sends to the database inside the block."""
    counter = StatementCounter()

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        counter.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
