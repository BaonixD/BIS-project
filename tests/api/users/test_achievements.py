import httpx
from sqlalchemy import select

from support.clock import ManualClock
from support.drivers import DriverFactory, login_as
from support.history import past_rides
from support.rides import RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.ratings.models import RaterRole, RideRating
from taxi_service.modules.rides.states import RideStatus


async def test_achievements_use_completed_history_and_exact_rating_threshold(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    driver_id = await driver_factory.driver("driver")
    passenger = await ride_factory.passenger("passenger")
    rides = await past_rides(
        ride_factory, passenger, 5, status=RideStatus.COMPLETED, driver_id=driver_id
    )
    async with session_factory.begin() as db:
        for ride_id, stars in zip(rides, [5, 5, 5, 5, 4], strict=True):
            db.add(
                RideRating(
                    ride_id=ride_id,
                    rater_id=passenger,
                    rater_role=RaterRole.PASSENGER,
                    ratee_id=driver_id,
                    stars=stars,
                    created_at=clock.now(),
                )
            )
    await login_as(client, "driver")
    result = (await client.get("/api/v1/users/me/achievements")).json()
    goals = {goal["code"]: goal for goal in result["achievements"]}
    assert result["completed_rides"] == 5
    assert goals["high_rating"]["unlocked"] is True
    assert goals["high_rating"]["current"] == 4.8
    assert goals["experienced_driver"]["unlocked"] is False
    async with session_factory.begin() as db:
        rating = await db.scalar(select(RideRating).where(RideRating.ride_id == rides[0]))
        assert rating is not None
        rating.stars = 3
    goals = {
        goal["code"]: goal
        for goal in (await client.get("/api/v1/users/me/achievements")).json()["achievements"]
    }
    assert goals["high_rating"]["unlocked"] is False
    await login_as(client, "passenger")
    result = (await client.get("/api/v1/users/me/achievements")).json()
    assert all(goal["unlocked"] for goal in result["achievements"])
    assert (await client.get("/api/v1/users/me/achievements")).json() == result
