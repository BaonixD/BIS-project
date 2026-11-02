"""find_nearby_candidates: approved, online, fresh location, within the radius, nearest first."""

import math
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from support.clock import ManualClock
from support.drivers import DriverFactory
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.drivers.candidates import Candidate, find_nearby_candidates
from taxi_service.modules.drivers.geodesy import EARTH_RADIUS_M, haversine_m
from taxi_service.modules.drivers.models import LOCATION_INDEX_NAME
from taxi_service.modules.geo.schemas import Coordinates

PICKUP = Coordinates(longitude=76.9457, latitude=43.2383)  # synthetic point in Almaty
METRES_PER_DEGREE = EARTH_RADIUS_M * math.pi / 180


def offset(origin: Coordinates, *, north_m: float = 0, east_m: float = 0) -> Coordinates:
    east_degree = METRES_PER_DEGREE * math.cos(math.radians(origin.latitude))
    return Coordinates(
        longitude=origin.longitude + east_m / east_degree,
        latitude=origin.latitude + north_m / METRES_PER_DEGREE,
    )


async def search(
    session_factory: SessionFactory, clock: ManualClock, pickup: Coordinates = PICKUP, **kw: Any
) -> list[Candidate]:
    async with session_factory() as session, read_transaction(session):
        return await find_nearby_candidates(session, pickup, now=clock.now(), **kw)


def ids(candidates: list[Candidate]) -> list[uuid.UUID]:
    return [candidate.driver_id for candidate in candidates]


async def test_nearest_driver_comes_first_with_distance_in_metres(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    far = await driver_factory.driver("far", location=offset(PICKUP, north_m=4000))
    near = await driver_factory.driver("near", location=offset(PICKUP, east_m=300))
    middle = await driver_factory.driver("middle", location=offset(PICKUP, north_m=-1200))

    found = await search(session_factory, clock)

    assert ids(found) == [near, middle, far]
    assert [round(candidate.distance_m) for candidate in found] == [300, 1200, 4000]


async def test_drivers_outside_the_radius_are_excluded(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    inside = await driver_factory.driver("inside", location=offset(PICKUP, north_m=4990))
    outside = await driver_factory.driver("outside", location=offset(PICKUP, east_m=5010))
    await driver_factory.driver("far_away", location=Coordinates(longitude=71.43, latitude=51.13))

    assert ids(await search(session_factory, clock)) == [inside]
    assert ids(await search(session_factory, clock, radius_m=6000)) == [inside, outside]


async def test_radius_boundary_is_inclusive(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    location = offset(PICKUP, north_m=3000, east_m=4000)
    driver = await driver_factory.driver("edge", location=location)
    exact = haversine_m(PICKUP, location)

    at_radius = await search(session_factory, clock, radius_m=exact)
    just_inside = await search(session_factory, clock, radius_m=math.nextafter(exact, 0))

    assert at_radius == [Candidate(driver_id=driver, distance_m=exact)]
    assert just_inside == []


async def test_location_older_than_sixty_seconds_is_stale(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    driver = await driver_factory.driver("dana", location=offset(PICKUP, east_m=100))

    clock.advance(timedelta(seconds=60))
    at_limit = await search(session_factory, clock)
    clock.advance(timedelta(microseconds=1))
    stale = await search(session_factory, clock)
    await driver_factory.move(driver, offset(PICKUP, east_m=100))
    refreshed = await search(session_factory, clock)

    assert (ids(at_limit), stale, ids(refreshed)) == ([driver], [], [driver])


async def test_maximum_location_age_is_a_parameter(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    driver = await driver_factory.driver("dana", location=offset(PICKUP, east_m=100))
    clock.advance(timedelta(seconds=30))

    assert await search(session_factory, clock, max_location_age_s=29) == []
    assert ids(await search(session_factory, clock, max_location_age_s=30)) == [driver]


async def test_equal_distance_is_ordered_by_driver_id(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    location = offset(PICKUP, north_m=500)
    drivers = [await driver_factory.driver(f"twin_{n}", location=location) for n in range(4)]

    found = await search(session_factory, clock)

    assert ids(found) == sorted(drivers)
    assert len({candidate.distance_m for candidate in found}) == 1


async def test_only_approved_online_located_drivers_are_candidates(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    near = offset(PICKUP, east_m=200)
    eligible = await driver_factory.driver("eligible", location=near)
    await driver_factory.driver("pending", location=near, approved=False)
    await driver_factory.driver("offline", location=near, online=False)
    await driver_factory.driver("no_location")
    went_offline = await driver_factory.driver("went_offline", location=near)
    await driver_factory.go_offline(went_offline)

    assert ids(await search(session_factory, clock)) == [eligible]


async def test_excluded_drivers_are_skipped(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    first = await driver_factory.driver("first", location=offset(PICKUP, east_m=100))
    second = await driver_factory.driver("second", location=offset(PICKUP, east_m=200))
    third = await driver_factory.driver("third", location=offset(PICKUP, east_m=300))

    found = await search(session_factory, clock, exclude_driver_ids={first, third})

    assert ids(found) == [second]


async def test_limit_keeps_the_nearest(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    drivers = [
        await driver_factory.driver(f"driver_{n}", location=offset(PICKUP, east_m=100 * n))
        for n in range(1, 5)
    ]

    assert ids(await search(session_factory, clock, limit=2)) == drivers[:2]
    assert ids(await search(session_factory, clock, limit=1)) == drivers[:1]


async def test_search_across_the_antimeridian(
    driver_factory: DriverFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    pickup = Coordinates(longitude=179.999, latitude=0)
    driver = await driver_factory.driver(
        "east", location=Coordinates(longitude=-179.999, latitude=0)
    )

    found = await search(session_factory, clock, pickup=pickup)

    assert ids(found) == [driver]
    assert found[0].distance_m == pytest.approx(222.4, abs=0.1)


@pytest.mark.parametrize(
    "arguments", [{"radius_m": 0}, {"radius_m": -1}, {"max_location_age_s": -1}, {"limit": 0}]
)
async def test_invalid_arguments_are_rejected(
    session_factory: SessionFactory, clock: ManualClock, arguments: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="must be"):
        await search(session_factory, clock, **arguments)


@pytest.fixture
def statements(engine: AsyncEngine) -> Iterator[list[tuple[str, Any]]]:
    captured: list[tuple[str, Any]] = []

    def capture(_conn: Any, _cursor: Any, statement: str, parameters: Any, *_: Any) -> None:
        if "driver_profiles" in statement:
            captured.append((statement, parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    yield captured
    event.remove(engine.sync_engine, "before_cursor_execute", capture)


async def test_query_prefilters_with_the_location_index(
    driver_factory: DriverFactory,
    session_factory: SessionFactory,
    clock: ManualClock,
    statements: list[tuple[str, Any]],
) -> None:
    await driver_factory.driver("dana", location=offset(PICKUP, east_m=100))
    statements.clear()

    await search(session_factory, clock)

    [(statement, parameters)] = statements
    async with session_factory() as session, read_transaction(session):
        connection = await session.connection()
        plan = await connection.exec_driver_sql(f"EXPLAIN QUERY PLAN {statement}", parameters)
        details = " ".join(str(row[-1]) for row in plan)
    assert LOCATION_INDEX_NAME in details
