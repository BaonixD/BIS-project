"""Database constraints of ride_ratings and ride_rating_tags, independent of the Python checks."""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from support.rows import NOW, insert, insert_driver, insert_ride
from taxi_service.database.session import SessionFactory


async def completed_ride(session_factory: SessionFactory) -> tuple[str, str, str]:
    """A completed ride: its id, passenger and driver."""
    driver_id = await insert_driver(session_factory)
    ride_id = await insert_ride(
        session_factory, status="completed", driver_id=driver_id, completed_at=NOW
    )
    async with session_factory.begin() as session:
        passenger_id = await session.scalar(
            text("SELECT passenger_id FROM rides WHERE id = :id"), {"id": ride_id}
        )
    return ride_id, str(passenger_id), driver_id


async def insert_rating(
    session_factory: SessionFactory,
    ride: tuple[str, str, str],
    *,
    rater_role: str = "passenger",
    **values: Any,
) -> str:
    ride_id, passenger_id, driver_id = ride
    rater, ratee = (
        (passenger_id, driver_id) if rater_role == "passenger" else (driver_id, passenger_id)
    )
    rating_id = uuid.uuid4().hex
    row = {
        "id": rating_id,
        "ride_id": ride_id,
        "rater_id": rater,
        "rater_role": rater_role,
        "ratee_id": ratee,
        "stars": 5,
        "comment": None,
        "created_at": NOW,
        **values,
    }
    await insert(session_factory, "ride_ratings", row)
    return rating_id


async def test_valid_ratings_of_both_sides_are_stored(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)

    rating_id = await insert_rating(session_factory, ride, stars=1, comment="x" * 500)
    await insert_rating(session_factory, ride, rater_role="driver")
    await insert(session_factory, "ride_rating_tags", {"rating_id": rating_id, "tag": "polite"})


@pytest.mark.parametrize(
    "values",
    [
        {"stars": 0},
        {"stars": 6},
        {"rater_role": "admin"},
        {"comment": "x" * 501},
        {"comment": ""},
    ],
)
async def test_rating_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_rating(session_factory, ride, **values)


async def test_one_rating_per_side_of_a_ride(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)
    await insert_rating(session_factory, ride)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_rating(session_factory, ride, stars=1)


async def test_nobody_rates_themselves(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_rating(session_factory, ride, ratee_id=ride[1])


async def test_rating_refers_to_an_existing_ride(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_rating(session_factory, ride, ride_id=uuid.uuid4().hex)


async def test_tags_are_known_and_unique_per_rating(session_factory: SessionFactory) -> None:
    rating_id = await insert_rating(session_factory, await completed_ride(session_factory))
    await insert(session_factory, "ride_rating_tags", {"rating_id": rating_id, "tag": "on_time"})

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert(session_factory, "ride_rating_tags", {"rating_id": rating_id, "tag": "rude"})
    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert(
            session_factory, "ride_rating_tags", {"rating_id": rating_id, "tag": "on_time"}
        )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert(
            session_factory, "ride_rating_tags", {"rating_id": uuid.uuid4().hex, "tag": "clean"}
        )
