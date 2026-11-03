"""Dispatch through the service with a manual clock (MVP_SPEC §6, ADR 0006).

The nearest candidate gets one offer for 30 seconds; rejection or expiry passes
the ride to the next one; nobody is asked twice in a search; no candidate or a
spent 180-second budget ends in ``no_driver``. Repeated and concurrent passes
never create a second offer or assignment.
"""

import asyncio
import math
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.rides import RideFactory
from support.rows import insert_ride
from taxi_service.database.session import SessionFactory
from taxi_service.modules.drivers.candidates import Candidate, find_nearby_candidates
from taxi_service.modules.drivers.geodesy import EARTH_RADIUS_M
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides import dispatch as dispatch_module
from taxi_service.modules.rides.dispatch import restart_search
from taxi_service.modules.rides.exceptions import (
    DriverBusyError,
    InvalidOfferTransitionError,
    OfferExpiredError,
    OfferNotFoundError,
)
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY
from taxi_service.modules.rides.states import OfferStatus, RideStatus

PICKUP = Coordinates(longitude=76.9457, latitude=43.2383)
METRES_PER_DEGREE = EARTH_RADIUS_M * math.pi / 180
TTL = timedelta(seconds=30)
JUST_BEFORE = TTL - timedelta(milliseconds=1)


def north(metres: float) -> Coordinates:
    return Coordinates(
        longitude=PICKUP.longitude, latitude=PICKUP.latitude + metres / METRES_PER_DEGREE
    )


def east(metres: float) -> Coordinates:
    east_degree = METRES_PER_DEGREE * math.cos(math.radians(PICKUP.latitude))
    return Coordinates(longitude=PICKUP.longitude + metres / east_degree, latitude=PICKUP.latitude)


async def statuses(dispatcher: Dispatcher, ride_id: object) -> list[tuple[str, OfferStatus]]:
    assert ride_id is not None
    return [
        (offer.driver_id.hex, offer.status)
        for offer in await dispatcher.offers(ride_id)  # type: ignore[arg-type]
    ]


# Choosing the candidate


async def test_nearest_driver_gets_a_30_second_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    await driver_factory.driver("far", location=north(3000))
    near = await driver_factory.driver("near", location=east(400))
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    processed = await dispatcher.process(ride.id)

    [offer] = await dispatcher.offers(ride.id)
    assert (offer.driver_id, offer.status) == (near, OfferStatus.PENDING)
    assert (offer.created_at, offer.expires_at, offer.responded_at) == (
        clock.now(),
        clock.now() + TTL,
        None,
    )
    assert processed is not None
    assert (processed.status, processed.driver_id) == (RideStatus.SEARCHING, None)


async def test_equal_distance_goes_to_the_lower_driver_id(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    first = await driver_factory.driver("first", location=east(500))
    second = await driver_factory.driver("second", location=east(500))
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    await dispatcher.process(ride.id)

    [offer] = await dispatcher.offers(ride.id)
    assert offer.driver_id == min(first, second)


async def test_ride_gets_its_search_window(ride_factory: RideFactory, clock: ManualClock) -> None:
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    assert (ride.search_started_at, ride.search_deadline) == (
        clock.now(),
        clock.now() + timedelta(seconds=180),
    )


async def test_stale_location_is_not_a_candidate(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    stale = await driver_factory.driver("stale", location=east(100))
    clock.advance(timedelta(seconds=61))
    fresh = await driver_factory.driver("fresh", location=north(4000))
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    await dispatcher.process(ride.id)

    assert [offer.driver_id for offer in await dispatcher.offers(ride.id)] == [fresh]
    assert stale != fresh


async def ineligible_driver(
    kind: str,
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    """One driver near the pickup that must not be offered a new ride."""
    if kind == "outside_radius":
        await driver_factory.driver(kind, location=north(5010))
    elif kind == "offline":
        await driver_factory.driver(kind, location=east(100), online=False)
    elif kind == "not_approved":
        await driver_factory.driver(kind, location=east(100), approved=False)
    elif kind == "stale":
        await driver_factory.driver(kind, location=east(100))
        clock.advance(timedelta(seconds=60, microseconds=1))
    elif kind in ("reserved", "busy"):
        driver = await driver_factory.driver(kind, location=east(100))
        other = await ride_factory.searching_ride(pickup=PICKUP)
        await dispatcher.process(other.id)
        [offer] = await dispatcher.offers(other.id)
        if kind == "busy":
            await dispatcher.accept(offer.id, driver)
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind", ["outside_radius", "offline", "not_approved", "stale", "reserved", "busy"]
)
async def test_ineligible_driver_gets_no_offer_and_the_ride_has_no_driver(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
    kind: str,
) -> None:
    await ineligible_driver(kind, driver_factory, ride_factory, dispatcher, clock)
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    processed = await dispatcher.process(ride.id)

    assert await dispatcher.offers(ride.id) == []
    assert processed is not None
    assert (processed.status, processed.driver_id) == (RideStatus.NO_DRIVER, None)
    assert (await dispatcher.ride(ride.id)).status is RideStatus.NO_DRIVER


async def test_location_exactly_60_seconds_old_still_counts(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    driver = await driver_factory.driver("edge", location=east(100))
    clock.advance(timedelta(seconds=60))
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    await dispatcher.process(ride.id)

    assert [offer.driver_id for offer in await dispatcher.offers(ride.id)] == [driver]


# Answers and timeouts


async def test_rejection_offers_the_ride_to_the_next_candidate_at_once(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    near = await driver_factory.driver("near", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(timedelta(seconds=5))

    rejected = await dispatcher.reject(offer.id, near)

    assert (rejected.status, rejected.responded_at) == (OfferStatus.REJECTED, clock.now())
    following = await dispatcher.pending(ride.id)
    assert following is not None
    assert (following.driver_id, following.expires_at) == (next_one, clock.now() + TTL)


async def test_timeout_offers_the_ride_to_the_next_candidate(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    near = await driver_factory.driver("near", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)

    clock.advance(JUST_BEFORE)
    assert await dispatcher.process_due() == 0
    clock.advance(TTL - JUST_BEFORE)
    assert await dispatcher.process_due() == 1

    first, second = await dispatcher.offers(ride.id)
    assert (first.driver_id, first.status, first.responded_at) == (
        near,
        OfferStatus.EXPIRED,
        clock.now(),
    )
    assert (second.driver_id, second.status) == (next_one, OfferStatus.PENDING)


async def test_accept_just_before_the_deadline_assigns_the_driver(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(JUST_BEFORE)

    assigned = await dispatcher.accept(offer.id, driver)

    assert (assigned.id, assigned.status, assigned.driver_id) == (
        ride.id,
        RideStatus.ASSIGNED,
        driver,
    )
    assert assigned.updated_at == clock.now()
    [stored] = await dispatcher.offers(ride.id)
    assert (stored.status, stored.responded_at) == (OfferStatus.ACCEPTED, clock.now())
    assert (await dispatcher.ride(ride.id)).driver_id == driver


async def test_accept_at_exactly_30_seconds_is_refused_and_marks_the_offer_expired(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(TTL)

    with pytest.raises(OfferExpiredError):
        await dispatcher.accept(offer.id, driver)

    assert await statuses(dispatcher, ride.id) == [
        (driver.hex, OfferStatus.EXPIRED),
        (next_one.hex, OfferStatus.PENDING),
    ]
    stored = await dispatcher.ride(ride.id)
    assert (stored.status, stored.driver_id) == (RideStatus.SEARCHING, None)


async def test_accepting_twice_returns_the_same_assignment(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    first = await dispatcher.accept(offer.id, driver)
    clock.advance(timedelta(minutes=5))

    again = await dispatcher.accept(offer.id, driver)

    assert (again.id, again.status, again.driver_id, again.updated_at) == (
        first.id,
        RideStatus.ASSIGNED,
        driver,
        first.updated_at,
    )


async def test_only_the_addressee_can_answer_an_offer(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    other = await driver_factory.driver("other", location=north(4000), online=False)
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)

    with pytest.raises(OfferNotFoundError):
        await dispatcher.accept(offer.id, other)
    with pytest.raises(OfferNotFoundError):
        await dispatcher.reject(offer.id, other)
    with pytest.raises(OfferNotFoundError):
        await dispatcher.accept(ride.id, driver)  # not an offer id

    assert await statuses(dispatcher, ride.id) == [(driver.hex, OfferStatus.PENDING)]


async def test_a_rejected_offer_cannot_be_accepted(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    await dispatcher.reject(offer.id, driver)

    with pytest.raises(InvalidOfferTransitionError):
        await dispatcher.accept(offer.id, driver)

    again = await dispatcher.reject(offer.id, driver)
    assert again.status is OfferStatus.REJECTED
    assert (await dispatcher.ride(ride.id)).status is RideStatus.NO_DRIVER


# End of the search


async def test_no_candidate_ends_the_search_at_once(
    ride_factory: RideFactory, dispatcher: Dispatcher, clock: ManualClock
) -> None:
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    processed = await dispatcher.process(ride.id)

    assert processed is not None
    assert (processed.status, processed.updated_at) == (RideStatus.NO_DRIVER, clock.now())


async def test_a_driver_who_said_no_is_not_asked_again_in_this_search(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    first = await driver_factory.driver("first", location=east(100))
    second = await driver_factory.driver("second", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(timedelta(seconds=1))
    await dispatcher.reject(offer.id, first)
    clock.advance(TTL)  # the second driver lets it expire

    await dispatcher.process_due()

    assert await statuses(dispatcher, ride.id) == [
        (first.hex, OfferStatus.REJECTED),
        (second.hex, OfferStatus.EXPIRED),
    ]
    assert (await dispatcher.ride(ride.id)).status is RideStatus.NO_DRIVER


async def test_search_budget_of_180_seconds_ends_in_no_driver(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    drivers = [
        await driver_factory.driver(f"driver_{index}", location=east(100 + 100 * index))
        for index in range(7)
    ]
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)

    async def wait_for_timeout() -> None:
        clock.advance(TTL)
        for index, driver in enumerate(drivers):  # drivers keep sending their location
            await driver_factory.move(driver, east(100 + 100 * index))
        await dispatcher.process_due()

    for _ in range(5):
        await wait_for_timeout()
        assert (await dispatcher.ride(ride.id)).status is RideStatus.SEARCHING
    await wait_for_timeout()  # 180 seconds since the ride was created

    assert await statuses(dispatcher, ride.id) == [
        (driver.hex, OfferStatus.EXPIRED) for driver in drivers[:6]
    ]
    assert (await dispatcher.ride(ride.id)).status is RideStatus.NO_DRIVER


async def test_offer_made_before_the_deadline_keeps_its_full_30_seconds(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    """The budget is checked before each new offer; the last one still runs 30 seconds."""
    first = await driver_factory.driver("first", location=east(100))
    second = await driver_factory.driver("second", location=east(500))
    late = await driver_factory.driver("late", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    clock.advance(timedelta(seconds=170))
    await driver_factory.move(second, east(500))
    await driver_factory.move(late, east(900))
    await dispatcher.process_due()  # the first offer expired at 30 s, unnoticed until now
    offer = await dispatcher.pending(ride.id)
    assert offer is not None
    await dispatcher.reject(offer.id, second)
    last = await dispatcher.pending(ride.id)
    assert last is not None
    assert last.expires_at == clock.now() + TTL
    clock.advance(timedelta(seconds=20))  # 190 s: past the budget, inside the offer

    assigned = await dispatcher.accept(last.id, late)

    assert (assigned.status, assigned.driver_id) == (RideStatus.ASSIGNED, late)
    assert first != assigned.driver_id


# Repeated and concurrent processing


async def test_processing_again_creates_no_second_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    await driver_factory.driver("near", location=east(100))
    await driver_factory.driver("other", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    clock.advance(timedelta(seconds=10))

    await dispatcher.process(ride.id)
    assert await dispatcher.process_due() == 0

    assert len(await dispatcher.offers(ride.id)) == 1


async def test_processing_a_finished_ride_changes_nothing(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    await driver_factory.driver("late", location=east(100))

    processed = await dispatcher.process(ride.id)

    assert processed is not None
    assert processed.status is RideStatus.NO_DRIVER
    assert await dispatcher.offers(ride.id) == []
    assert await dispatcher.process_due() == 0


async def test_two_simultaneous_passes_create_one_offer(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    await driver_factory.driver("near", location=east(100))
    await driver_factory.driver("other", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    await asyncio.gather(dispatcher.process(ride.id), dispatcher.process(ride.id))
    await asyncio.gather(dispatcher.process_due(), dispatcher.process_due())

    assert len(await dispatcher.offers(ride.id)) == 1


async def test_one_driver_is_offered_only_one_of_two_rides(
    driver_factory: DriverFactory, ride_factory: RideFactory, dispatcher: Dispatcher
) -> None:
    driver = await driver_factory.driver("only", location=east(100))
    first = await ride_factory.searching_ride(pickup=PICKUP)
    second = await ride_factory.searching_ride(pickup=PICKUP)

    await asyncio.gather(dispatcher.process(first.id), dispatcher.process(second.id))

    [offer] = await dispatcher.offers(driver_id=driver)
    assert offer.status is OfferStatus.PENDING
    other = second.id if offer.ride_id == first.id else first.id
    assert (await dispatcher.ride(other)).status is RideStatus.NO_DRIVER


async def test_two_drivers_never_get_the_same_ride(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    late = await driver_factory.driver("late", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [old] = await dispatcher.offers(ride.id)
    clock.advance(TTL)
    await dispatcher.process_due()
    new = await dispatcher.pending(ride.id)
    assert new is not None

    results = await asyncio.gather(
        dispatcher.accept(old.id, late), dispatcher.accept(new.id, next_one), return_exceptions=True
    )

    assert isinstance(results[0], OfferExpiredError)
    assert not isinstance(results[1], BaseException)
    stored = await dispatcher.ride(ride.id)
    assert (stored.status, stored.driver_id) == (RideStatus.ASSIGNED, next_one)


@pytest.mark.parametrize(
    ("elapsed", "accepted"), [(JUST_BEFORE, True), (TTL, False)], ids=["before", "at_deadline"]
)
async def test_simultaneous_accept_and_expiry_agree(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
    elapsed: timedelta,
    accepted: bool,
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(elapsed)

    accept, _ = await asyncio.gather(
        dispatcher.accept(offer.id, driver), dispatcher.process_due(), return_exceptions=True
    )

    stored = await dispatcher.ride(ride.id)
    if accepted:
        assert not isinstance(accept, BaseException)
        assert (stored.status, stored.driver_id) == (RideStatus.ASSIGNED, driver)
        assert await statuses(dispatcher, ride.id) == [(driver.hex, OfferStatus.ACCEPTED)]
    else:
        assert isinstance(accept, OfferExpiredError)
        assert (stored.status, stored.driver_id) == (RideStatus.SEARCHING, None)
        assert await statuses(dispatcher, ride.id) == [
            (driver.hex, OfferStatus.EXPIRED),
            (next_one.hex, OfferStatus.PENDING),
        ]


async def test_a_lost_reservation_race_moves_on_to_the_next_candidate(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidates read before a concurrent commit: the unique index refuses the offer."""
    taken = await driver_factory.driver("taken", location=east(100))
    free = await driver_factory.driver("free", location=east(900))
    other = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(other.id)
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    async def stale_candidates(*args: Any, **kwargs: Any) -> list[Candidate]:
        found = await find_nearby_candidates(*args, **kwargs)
        return [Candidate(driver_id=taken, distance_m=100.0), *found]

    monkeypatch.setattr(dispatch_module, "find_nearby_candidates", stale_candidates)

    await dispatcher.process(ride.id)

    assert await statuses(dispatcher, ride.id) == [(free.hex, OfferStatus.PENDING)]
    assert await statuses(dispatcher, other.id) == [(taken.hex, OfferStatus.PENDING)]


# Driver leaves


async def test_going_offline_revokes_the_pending_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    leaving = await driver_factory.driver("leaving", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(timedelta(seconds=5))

    await driver_factory.go_offline(leaving)
    with pytest.raises(InvalidOfferTransitionError):
        await dispatcher.accept(offer.id, leaving)
    await dispatcher.process_due()

    assert await statuses(dispatcher, ride.id) == [
        (leaving.hex, OfferStatus.REVOKED),
        (next_one.hex, OfferStatus.PENDING),
    ]


async def test_losing_approval_revokes_the_pending_offer(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    from taxi_service.modules.drivers import service as driver_service
    from taxi_service.modules.drivers.schemas import DriverProfileUpdate

    driver = await driver_factory.driver("driver", location=east(100))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)

    async with session_factory() as session:
        await driver_service.update_profile(
            session, driver, DriverProfileUpdate(full_name="Another Name"), clock=clock
        )

    assert await statuses(dispatcher, ride.id) == [(driver.hex, OfferStatus.REVOKED)]


# Answers that come too late or conflict


async def test_reject_after_the_deadline_is_refused_and_moves_on(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    clock: ManualClock,
) -> None:
    driver = await driver_factory.driver("driver", location=east(100))
    next_one = await driver_factory.driver("next", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    clock.advance(TTL)

    with pytest.raises(OfferExpiredError):
        await dispatcher.reject(offer.id, driver)

    assert await statuses(dispatcher, ride.id) == [
        (driver.hex, OfferStatus.EXPIRED),
        (next_one.hex, OfferStatus.PENDING),
    ]


async def test_accept_by_a_driver_who_got_another_ride_meanwhile_is_a_conflict(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    """Only the one-active-ride index stops it (state written behind dispatch's back)."""
    driver = await driver_factory.driver("driver", location=east(100))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [offer] = await dispatcher.offers(ride.id)
    await insert_ride(session_factory, status="assigned", driver_id=driver.hex)

    with pytest.raises(DriverBusyError):
        await dispatcher.accept(offer.id, driver)

    stored = await dispatcher.ride(ride.id)
    assert (stored.status, stored.driver_id) == (RideStatus.SEARCHING, None)
    assert await statuses(dispatcher, ride.id) == [(driver.hex, OfferStatus.PENDING)]


async def test_an_integrity_error_other_than_a_lost_race_is_not_hidden(
    ride_factory: RideFactory, dispatcher: Dispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the pending/search unique indexes mean "taken"; a broken reference surfaces."""
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    async def unknown_driver(*args: Any, **kwargs: Any) -> list[Candidate]:
        return [Candidate(driver_id=uuid.uuid4(), distance_m=100.0)]

    monkeypatch.setattr(dispatch_module, "find_nearby_candidates", unknown_driver)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await dispatcher.process(ride.id)

    assert await dispatcher.offers(ride.id) == []
    assert (await dispatcher.ride(ride.id)).status is RideStatus.SEARCHING


# A new search after release (T07B performs the release itself)


async def release(session_factory: SessionFactory, clock: ManualClock, ride_id: uuid.UUID) -> Ride:
    """What T07B's release does in its transaction: back to searching, new search window."""
    async with session_factory() as session, session.begin():
        ride = await session.get(Ride, ride_id, with_for_update=True)
        assert ride is not None
        ride.status = RideStatus.SEARCHING
        ride.driver_id = None
        ride.updated_at = clock.now()
        restart_search(ride, clock.now(), DEFAULT_DISPATCH_POLICY)
    return ride


async def test_after_release_a_new_search_may_ask_earlier_drivers_but_not_the_releaser(
    driver_factory: DriverFactory,
    ride_factory: RideFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    refuser = await driver_factory.driver("refuser", location=east(100))
    releaser = await driver_factory.driver("releaser", location=east(900))
    ride = await ride_factory.searching_ride(pickup=PICKUP)
    await dispatcher.process(ride.id)
    [first] = await dispatcher.offers(ride.id)
    clock.advance(timedelta(seconds=1))
    await dispatcher.reject(first.id, refuser)
    second = await dispatcher.pending(ride.id)
    assert second is not None
    await dispatcher.accept(second.id, releaser)
    clock.advance(timedelta(seconds=10))

    restarted = await release(session_factory, clock, ride.id)
    await dispatcher.process(ride.id)

    assert (restarted.search_started_at, restarted.search_deadline) == (
        clock.now(),
        clock.now() + timedelta(seconds=180),
    )
    again = await dispatcher.pending(ride.id)
    assert again is not None
    assert again.driver_id == refuser
    clock.advance(timedelta(seconds=1))
    await dispatcher.reject(again.id, refuser)  # asked once in this search: not again
    assert (await dispatcher.ride(ride.id)).status is RideStatus.NO_DRIVER


async def test_a_new_search_starts_strictly_after_the_previous_one(
    ride_factory: RideFactory, session_factory: SessionFactory, clock: ManualClock
) -> None:
    ride = await ride_factory.searching_ride(pickup=PICKUP)

    restarted = await release(session_factory, clock, ride.id)  # same clock reading

    assert restarted.search_started_at > ride.search_started_at
