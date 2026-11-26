import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import update

from support.clock import ManualClock
from support.drivers import DriverFactory, login_as
from support.history import past_rides
from support.rides import RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from taxi_service.modules.ratings.models import RaterRole, RideRating
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.tariffs import Tariff

URL = "/api/v1/users/me/achievements"


def utc(day: int, hour: int, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


async def finish(
    session_factory: SessionFactory, ride_id: uuid.UUID, completed_at: datetime, **values: Any
) -> None:
    async with session_factory.begin() as db:
        await db.execute(
            update(Ride).where(Ride.id == ride_id).values(completed_at=completed_at, **values)
        )


async def pay_by_kaspi(session_factory: SessionFactory, ride_id: uuid.UUID, at: datetime) -> None:
    async with session_factory.begin() as db:
        await db.execute(
            update(Payment)
            .where(Payment.ride_id == ride_id)
            .values(method=PaymentMethod.KASPI_LINK, status=PaymentStatus.PAID, paid_at=at)
        )


async def progress(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get(URL)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_passenger_earns_xp_levels_streaks_and_the_weekly_quest(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    session_factory: SessionFactory,
) -> None:
    driver_id = await driver_factory.driver("driver")
    passenger = await ride_factory.passenger("passenger")
    rides = await past_rides(
        ride_factory, passenger, 6, status=RideStatus.COMPLETED, driver_id=driver_id
    )
    # Almaty is UTC+5; the clock stands on Tuesday 3 November, the week began on Monday.
    await finish(session_factory, rides[0], utc(8, 10, month=10))
    await finish(session_factory, rides[1], utc(21, 10, month=10), tariff=Tariff.BUSINESS)
    await finish(session_factory, rides[2], utc(28, 10, month=10), bonus_kzt=100)
    await finish(session_factory, rides[3], utc(2, 18))  # 23:00 in Almaty: a night ride
    await finish(session_factory, rides[4], utc(3, 8))
    await finish(session_factory, rides[5], utc(3, 8))
    await pay_by_kaspi(session_factory, rides[4], utc(3, 7))
    await pay_by_kaspi(session_factory, rides[5], utc(3, 7))
    await past_rides(ride_factory, passenger, 1, status=RideStatus.CANCELLED)

    await login_as(client, "passenger")
    body = await progress(client)

    goals = {goal["code"]: goal for goal in body["achievements"]}
    unlocked = {code for code, goal in goals.items() if goal["unlocked"]}
    assert unlocked == {
        "first_ride",
        "regular_passenger",
        "explorer",
        "night_owl",
        "premium",
        "bonus_saver",
    }
    assert set(goals) == unlocked | {"loyal_passenger", "feedback", "kaspi_fan", "streak_keeper"}
    assert goals["explorer"]["current"] == 60
    assert goals["kaspi_fan"]["current"] == 2
    assert goals["streak_keeper"]["current"] == 3
    assert all(goal["xp"] == 50 for goal in goals.values())
    assert body["streak"] == {"current_weeks": 3, "best_weeks": 3, "active_this_week": True}
    quest = body["weekly_quest"]
    assert (quest["current"], quest["target"], quest["completed"]) == (3, 3, True)
    assert quest["reward_xp"] == 150
    assert datetime.fromisoformat(quest["ends_at"]) == utc(8, 19)
    # 6 rides × 100 + 60 km × 2 + 6 achievements × 50 + one completed weekly quest × 150
    assert body["xp"] == 1170
    assert body["level"] == {"number": 3, "level_start_xp": 800, "next_level_xp": 1500}


async def test_driver_progress_counts_five_star_ratings_and_a_bigger_weekly_quest(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    driver_id = await driver_factory.driver("driver")
    passenger = await ride_factory.passenger("passenger")
    rides = await past_rides(
        ride_factory, passenger, 2, status=RideStatus.COMPLETED, driver_id=driver_id
    )
    async with session_factory.begin() as db:
        for ride_id in rides:
            db.add(
                RideRating(
                    ride_id=ride_id,
                    rater_id=passenger,
                    rater_role=RaterRole.PASSENGER,
                    ratee_id=driver_id,
                    stars=5,
                    created_at=clock.now(),
                )
            )

    await login_as(client, "driver")
    body = await progress(client)

    goals = {goal["code"]: goal for goal in body["achievements"]}
    assert set(goals) == {
        "first_order",
        "experienced_driver",
        "road_master",
        "high_rating",
        "marathon",
        "night_shift",
        "five_stars",
        "streak_keeper",
    }
    assert goals["five_stars"]["current"] == 2
    assert goals["marathon"]["current"] == 20
    assert body["weekly_quest"]["target"] == 10
    assert body["weekly_quest"]["current"] == 2
    assert body["streak"]["current_weeks"] == 1
    # 2 rides × 100 + 20 km × 2 + 2 five-star ratings × 20 + first_order × 50
    assert body["xp"] == 330
    assert body["level"]["number"] == 2


async def test_a_new_passenger_starts_at_level_one_without_a_streak(
    client: httpx.AsyncClient, ride_factory: RideFactory
) -> None:
    await ride_factory.passenger("newcomer")
    await login_as(client, "newcomer")
    body = await progress(client)
    assert body["xp"] == 0
    assert body["level"] == {"number": 1, "level_start_xp": 0, "next_level_xp": 300}
    assert body["streak"] == {"current_weeks": 0, "best_weeks": 0, "active_this_week": False}
    assert body["weekly_quest"]["current"] == 0
    assert not any(goal["unlocked"] for goal in body["achievements"])
