import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.drivers import service as drivers_service
from taxi_service.modules.drivers.models import DriverProfile
from taxi_service.modules.geo.client import RoutingProvider
from taxi_service.modules.geo.schemas import Coordinates, RouteResult
from taxi_service.modules.geo.service import plan_road_route
from taxi_service.modules.payments import records as payment_records
from taxi_service.modules.payments.exceptions import KaspiUnavailableError
from taxi_service.modules.payments.models import PaymentMethod
from taxi_service.modules.ratings import records as rating_records
from taxi_service.modules.ratings.models import RideRating
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.rides import dispatch
from taxi_service.modules.rides.exceptions import (
    ActiveRideExistsError,
    IdempotencyKeyReusedError,
    QuoteAlreadyUsedError,
    QuoteExpiredError,
    QuoteNotFoundError,
    RideNotFoundError,
)
from taxi_service.modules.rides.idempotency import request_fingerprint
from taxi_service.modules.rides.models import (
    ACCEPTED_ACTIVE_RIDE_STATUSES,
    QUOTE_AMOUNT_COLUMNS,
    IdempotencyRecord,
    Ride,
    RideQuote,
)
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.pricing import Fares, calculate_fares
from taxi_service.modules.rides.schemas import QuoteRequest, RideCreateRequest
from taxi_service.modules.rides.states import ACTIVE_RIDE_STATUSES, RideStatus
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.service import require_account_access

QUOTE_TTL: Final = timedelta(minutes=5)
DRIVER_CARD_STATUSES: Final = ACCEPTED_ACTIVE_RIDE_STATUSES | {RideStatus.COMPLETED}
CREATE_RIDE_OPERATION: Final = "create_ride"


@dataclass(frozen=True, slots=True)
class RideDetails:
    """``driver_rating`` is set with ``driver``; ``my_rating`` is the viewer's own.

    ``driver_location``: the card shows the driver's location (only while the ride is active).
    """

    ride: Ride
    driver: DriverProfile | None
    driver_rating: RatingSummary | None
    my_rating: RideRating | None
    driver_location: bool


@dataclass(frozen=True, slots=True)
class RideCreation:
    """``replayed``: an earlier request with the same key created ``ride``."""

    ride: Ride
    replayed: bool


async def create_quote(
    db: AsyncSession,
    passenger_id: uuid.UUID,
    request: QuoteRequest,
    *,
    clock: Clock,
    routing: RoutingProvider,
) -> RideQuote:
    """The route is planned outside the transaction; the five minutes start after it."""
    route = await plan_road_route(request.pickup, request.dropoff, routing=routing)
    fares = calculate_fares(distance_m=route.distance_m, duration_s=route.duration_s)
    now = clock.now()
    quote = RideQuote(
        id=uuid.uuid4(),
        passenger_id=passenger_id,
        **route_snapshot(request.pickup, request.dropoff, route, fares),
        **{QUOTE_AMOUNT_COLUMNS[tariff]: amount for tariff, amount in fares.amounts.items()},
        created_at=now,
        expires_at=now + QUOTE_TTL,
    )
    async with db.begin():
        db.add(quote)
        await db.flush()
    return quote


async def order_ride(
    db: AsyncSession,
    passenger_id: uuid.UUID,
    request: RideCreateRequest,
    key: str,
    *,
    clock: Clock,
    policy: DispatchPolicy,
    kaspi_enabled: bool,
) -> RideCreation:
    """Create the ride, then run its first search step; a replay does not search again."""
    creation = await create_ride(
        db, passenger_id, request, key, clock=clock, policy=policy, kaspi_enabled=kaspi_enabled
    )
    if creation.replayed:
        return creation
    ride = await dispatch.start_search(db, creation.ride.id, clock=clock, policy=policy)
    return RideCreation(ride, replayed=False)


async def create_ride(
    db: AsyncSession,
    passenger_id: uuid.UUID,
    request: RideCreateRequest,
    key: str,
    *,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    kaspi_enabled: bool = False,
) -> RideCreation:
    """A ``searching`` ride from the passenger's own valid quote and its payment, once per key."""
    # Defaults are left out: an omitted field and its explicit default are the same request.
    fingerprint = request_fingerprint(request.model_dump(mode="json", exclude_defaults=True))
    try:
        async with db.begin():
            replayed = await _replay(db, passenger_id, key, fingerprint)
            if replayed is not None:
                return RideCreation(replayed, replayed=True)
            if request.payment_method is PaymentMethod.KASPI_LINK and not kaspi_enabled:
                raise KaspiUnavailableError
            await require_account_access(db, passenger_id)
            ride = await _ride_from_quote(db, passenger_id, request, clock, policy)
            await payment_records.open_payment(db, ride, request.payment_method, ride.created_at)
            db.add(
                IdempotencyRecord(
                    id=uuid.uuid4(),
                    user_id=passenger_id,
                    operation=CREATE_RIDE_OPERATION,
                    key=key,
                    request_fingerprint=fingerprint,
                    resource_id=ride.id,
                    created_at=ride.created_at,
                )
            )
            await db.flush()
    except IntegrityError as error:
        return await _after_conflict(db, passenger_id, request, key, fingerprint, error)
    return RideCreation(ride, replayed=False)


async def get_ride(
    db: AsyncSession, ride_id: uuid.UUID, *, viewer_id: uuid.UUID, viewer_role: UserRole
) -> RideDetails:
    async with read_transaction(db):
        ride = await db.get(Ride, ride_id)
        if ride is None or not can_view_ride(ride, viewer_id, viewer_role):
            raise RideNotFoundError
        driver = driver_rating = None
        if ride.driver_id is not None and shows_driver(ride, viewer_id):
            driver = await drivers_service.get_driver_profile(db, ride.driver_id)
            driver_rating = await rating_records.summary(db, ride.driver_id)
        my_rating = await rating_records.rating_by(db, ride.id, viewer_id)
    driver_location = ride.status in ACCEPTED_ACTIVE_RIDE_STATUSES
    return RideDetails(ride, driver, driver_rating, my_rating, driver_location)


async def driver_has_active_ride(db: AsyncSession, driver_id: uuid.UUID) -> bool:
    """Assigned, arrived or in_progress; runs in the caller's transaction."""
    found = await db.scalar(
        select(Ride.id).where(
            Ride.driver_id == driver_id, Ride.status.in_(ACCEPTED_ACTIVE_RIDE_STATUSES)
        )
    )
    return found is not None


def can_view_ride(ride: Ride, viewer_id: uuid.UUID, viewer_role: UserRole) -> bool:
    """Admins, the passenger and the driver assigned now (not a released one)."""
    return viewer_role is UserRole.ADMIN or viewer_id in (ride.passenger_id, ride.driver_id)


def shows_driver(ride: Ride, viewer_id: uuid.UUID) -> bool:
    """To the participants of an active ride and, for the receipt, of a completed one."""
    participant = viewer_id in (ride.passenger_id, ride.driver_id)
    return participant and ride.status in DRIVER_CARD_STATUSES


def route_snapshot(
    pickup: Coordinates, dropoff: Coordinates, route: RouteResult, fares: Fares
) -> dict[str, Any]:
    return {
        "pickup_longitude": pickup.longitude,
        "pickup_latitude": pickup.latitude,
        "dropoff_longitude": dropoff.longitude,
        "dropoff_latitude": dropoff.latitude,
        "distance_m": route.distance_m,
        "duration_s": route.duration_s,
        "route_geometry": route.route_geometry.model_dump(mode="json"),
        "provider": route.provider,
        "currency": fares.currency,
        "tariff_version": fares.tariff_version,
    }


async def _replay(db: AsyncSession, user_id: uuid.UUID, key: str, fingerprint: str) -> Ride | None:
    record = await _get_idempotency_record(db, user_id, CREATE_RIDE_OPERATION, key)
    if record is None:
        return None
    if record.request_fingerprint != fingerprint:
        raise IdempotencyKeyReusedError
    ride = await db.get(Ride, record.resource_id)
    if ride is None:
        raise RuntimeError("Idempotency record refers to a missing ride")
    return ride


async def _ride_from_quote(
    db: AsyncSession,
    passenger_id: uuid.UUID,
    request: RideCreateRequest,
    clock: Clock,
    policy: DispatchPolicy,
) -> Ride:
    quote = await db.get(RideQuote, request.quote_id)
    if quote is None or quote.passenger_id != passenger_id:
        raise QuoteNotFoundError
    if await _quote_is_used(db, quote.id):
        raise QuoteAlreadyUsedError
    now = clock.now()
    if now >= quote.expires_at:
        raise QuoteExpiredError
    if await _has_active_ride(db, passenger_id):
        raise ActiveRideExistsError
    ride = Ride.from_quote(quote, request.tariff, now, search_budget=policy.search_budget)
    db.add(ride)
    await db.flush()
    return ride


async def _after_conflict(
    db: AsyncSession,
    passenger_id: uuid.UUID,
    request: RideCreateRequest,
    key: str,
    fingerprint: str,
    error: IntegrityError,
) -> RideCreation:
    """Explain a lost constraint race with the rows the winner committed."""
    async with read_transaction(db):
        replayed = await _replay(db, passenger_id, key, fingerprint)
        if replayed is not None:
            return RideCreation(replayed, replayed=True)
        if await _quote_is_used(db, request.quote_id):
            raise QuoteAlreadyUsedError from error
        if await _has_active_ride(db, passenger_id):
            raise ActiveRideExistsError from error
    raise error


async def _get_idempotency_record(
    db: AsyncSession, user_id: uuid.UUID, operation: str, key: str
) -> IdempotencyRecord | None:
    return await db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )


async def _quote_is_used(db: AsyncSession, quote_id: uuid.UUID) -> bool:
    found = await db.scalar(select(Ride.id).where(Ride.quote_id == quote_id))
    return found is not None


async def _has_active_ride(db: AsyncSession, passenger_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(Ride.id).where(
            Ride.passenger_id == passenger_id, Ride.status.in_(ACTIVE_RIDE_STATUSES)
        )
    )
    return found is not None
