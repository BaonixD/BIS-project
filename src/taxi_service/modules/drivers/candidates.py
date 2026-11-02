"""Nearest available drivers for a pickup point: the contract used by dispatch (T06).

A candidate is an approved, online driver with a vehicle whose last location
is at most ``max_location_age_s`` old and within ``radius_m`` of the pickup
(MVP_SPEC section 6). SQL selects rows inside the bounding box of the circle
using the (longitude, latitude) index; Python computes the haversine distance,
drops points outside the circle and orders by distance, then driver id.

Drivers who are busy (an accepted active ride: assigned, arrived,
in_progress) or reserved (a pending offer for any ride) are excluded in SQL,
inside the caller's transaction. With ``for_ride_id`` every driver who has
already had an offer for that ride is excluded too: a search never asks the
same driver twice (ADR 0006).
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Exists, Select, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.drivers.geodesy import BoundingBox, bounding_box, haversine_m
from taxi_service.modules.drivers.models import ApprovalStatus, DriverProfile, Vehicle
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.rides.models import ACCEPTED_ACTIVE_RIDE_STATUSES, Ride, RideOffer
from taxi_service.modules.rides.states import OfferStatus

DEFAULT_RADIUS_M = 5000.0
DEFAULT_MAX_LOCATION_AGE_S = 60.0
DEFAULT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class Candidate:
    driver_id: uuid.UUID
    """User id of the driver (``driver_profiles.user_id``)."""
    distance_m: float
    """Great-circle distance to the pickup in metres, not rounded."""


async def find_nearby_candidates(
    session: AsyncSession,
    pickup: Coordinates,
    *,
    now: datetime,
    radius_m: float = DEFAULT_RADIUS_M,
    max_location_age_s: float = DEFAULT_MAX_LOCATION_AGE_S,
    exclude_driver_ids: Collection[uuid.UUID] = (),
    for_ride_id: uuid.UUID | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    """At most ``limit`` candidates, nearest first; equal distances by ascending driver id.

    Both boundaries are inclusive: distance ``== radius_m`` and location age
    ``== max_location_age_s`` qualify. ``now`` is the caller's server time
    (``Clock``). Runs in the caller's transaction (``read_transaction`` or the
    dispatch service's ``session.begin()``); it neither begins nor commits.
    """
    if radius_m <= 0 or max_location_age_s < 0 or limit < 1:
        raise ValueError("radius_m must be > 0, max_location_age_s >= 0 and limit >= 1")
    fresh_since = now - timedelta(seconds=max_location_age_s)
    query = eligible_drivers(fresh_since).where(_inside(bounding_box(pickup, radius_m)))
    if exclude_driver_ids:
        query = query.where(DriverProfile.user_id.not_in(list(exclude_driver_ids)))
    if for_ride_id is not None:
        query = query.where(~_offered(for_ride_id))
    candidates = []
    for driver_id, longitude, latitude in await session.execute(query):
        if longitude is None or latitude is None:  # excluded by SQL; narrows the type
            continue
        distance = haversine_m(pickup, Coordinates(longitude=longitude, latitude=latitude))
        if distance <= radius_m:
            candidates.append(Candidate(driver_id=driver_id, distance_m=distance))
    candidates.sort(key=lambda candidate: (candidate.distance_m, candidate.driver_id))
    return candidates[:limit]


def eligible_drivers(fresh_since: datetime) -> Select[uuid.UUID, float | None, float | None]:
    """Approved, online, not busy or reserved drivers with a vehicle and a fresh location.

    The location must not be older than ``fresh_since``.
    """
    return (
        select(DriverProfile.user_id, DriverProfile.longitude, DriverProfile.latitude)
        .join(Vehicle, Vehicle.driver_id == DriverProfile.user_id)
        .where(
            DriverProfile.approval_status == ApprovalStatus.APPROVED,
            DriverProfile.is_online.is_(True),
            DriverProfile.location_updated_at >= fresh_since,
            ~_busy(),
            ~_reserved(),
        )
    )


def _busy() -> Exists:
    return exists().where(
        Ride.driver_id == DriverProfile.user_id,
        Ride.status.in_(ACCEPTED_ACTIVE_RIDE_STATUSES),
    )


def _reserved() -> Exists:
    return exists().where(
        RideOffer.driver_id == DriverProfile.user_id,
        RideOffer.status == OfferStatus.PENDING,
    )


def _offered(ride_id: uuid.UUID) -> Exists:
    return exists().where(
        RideOffer.ride_id == ride_id, RideOffer.driver_id == DriverProfile.user_id
    )


def _inside(box: BoundingBox) -> ColumnElement[bool]:
    longitude = or_(
        *(DriverProfile.longitude.between(low, high) for low, high in box.longitude_ranges)
    )
    return and_(DriverProfile.latitude.between(box.min_latitude, box.max_latitude), longitude)
