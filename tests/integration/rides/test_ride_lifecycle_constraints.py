"""Schema of the ride lifecycle: stage times and cancel reason of rides, the ride_events history.

Rows are inserted with raw SQL, so only the schema can accept or reject them.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from support.rows import NOW, insert_driver, insert_event, insert_ride, insert_user
from taxi_service.database.session import SessionFactory

STAGE_TIMES = ("assigned_at", "arrived_at", "started_at", "completed_at", "cancelled_at")
UNKNOWN_ID = "0" * 32


async def test_a_new_ride_has_no_stage_times_and_no_cancel_reason(
    session_factory: SessionFactory,
) -> None:
    ride = await insert_ride(session_factory)

    async with session_factory.begin() as session:
        row = (
            await session.execute(
                text(f"SELECT {', '.join(STAGE_TIMES)}, cancel_reason FROM rides WHERE id = :id"),
                {"id": ride},
            )
        ).one()

    assert tuple(row) == (None,) * (len(STAGE_TIMES) + 1)


async def test_a_finished_ride_keeps_its_stage_times(session_factory: SessionFactory) -> None:
    driver = await insert_driver(session_factory)

    await insert_ride(
        session_factory,
        status="completed",
        driver_id=driver,
        **dict.fromkeys(("assigned_at", "arrived_at", "started_at", "completed_at"), NOW),
    )
    await insert_ride(
        session_factory, status="cancelled", cancelled_at=NOW, cancel_reason="plans changed"
    )


async def test_an_event_records_a_transition(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)
    actor = await insert_user(session_factory)

    await insert_event(session_factory, ride)
    await insert_event(session_factory, ride, actor_id=actor, reason="plans changed")


@pytest.mark.parametrize("column", ["from_status", "to_status", "command", "created_at"])
async def test_event_fields_are_required(session_factory: SessionFactory, column: str) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_event(session_factory, ride, **{column: None})


async def test_event_belongs_to_a_ride(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_event(session_factory, None)


@pytest.mark.parametrize(
    "values",
    [
        {"from_status": "waiting"},
        {"to_status": "paid"},
        {"command": "teleport"},
        {"reason": ""},
        {"reason": "x" * 201},
    ],
)
async def test_event_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_event(session_factory, ride, **values)


async def test_event_reason_may_have_200_characters(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)

    await insert_event(session_factory, ride, reason="x" * 200)


async def test_event_ride_must_exist(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_event(session_factory, UNKNOWN_ID)


async def test_event_actor_must_exist(session_factory: SessionFactory) -> None:
    ride = await insert_ride(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_event(session_factory, ride, actor_id=UNKNOWN_ID)
