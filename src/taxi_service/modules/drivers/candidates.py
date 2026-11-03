"""Nearest available drivers: bounding box in SQL, haversine in Python (MVP_SPEC §6, ADR 0001)."""

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
class SearchScope:
    ride_id: uuid.UUID
    started_at: datetime


@dataclass(frozen=True, slots=True)
class Candidate:
    driver_id: uuid.UUID
    distance_m: float  # great-circle, not rounded


async def find_nearby_candidates(
    session: AsyncSession,
    pickup: Coordinates,
    *,
    now: datetime,
    radius_m: float = DEFAULT_RADIUS_M,
    max_location_age_s: float = DEFAULT_MAX_LOCATION_AGE_S,
    exclude_driver_ids: Collection[uuid.UUID] = (),
    in_search: SearchScope | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    """Nearest first, then by driver id; both boundaries inclusive; the caller's transaction."""
    if radius_m <= 0 or max_location_age_s < 0 or limit < 1:
        raise ValueError("radius_m must be > 0, max_location_age_s >= 0 and limit >= 1")
    fresh_since = now - timedelta(seconds=max_location_age_s)
    query = eligible_drivers(fresh_since).where(_inside(bounding_box(pickup, radius_m)))
    if exclude_driver_ids:
        query = query.where(DriverProfile.user_id.not_in(list(exclude_driver_ids)))
    if in_search is not None:
        query = query.where(~_considered(in_search))
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
    """Approved, online, free drivers with a vehicle and a location since ``fresh_since``."""
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


def _considered(search: SearchScope) -> Exists:
    """Asked in this search, or accepted the ride earlier (and released it since)."""
    return exists().where(
        RideOffer.ride_id == search.ride_id,
        RideOffer.driver_id == DriverProfile.user_id,
        or_(
            RideOffer.search_started_at == search.started_at,
            RideOffer.status == OfferStatus.ACCEPTED,
        ),
    )


def _inside(box: BoundingBox) -> ColumnElement[bool]:
    longitude = or_(
        *(DriverProfile.longitude.between(low, high) for low, high in box.longitude_ranges)
    )
    return and_(DriverProfile.latitude.between(box.min_latitude, box.max_latitude), longitude)
