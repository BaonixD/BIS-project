"""Nearest available drivers for a pickup point: the contract used by dispatch (T06)."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.geo.schemas import Coordinates

DEFAULT_RADIUS_M = 5000.0
DEFAULT_MAX_LOCATION_AGE_S = 60.0
DEFAULT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class Candidate:
    driver_id: uuid.UUID
    distance_m: float


async def find_nearby_candidates(
    session: AsyncSession,
    pickup: Coordinates,
    *,
    now: datetime,
    radius_m: float = DEFAULT_RADIUS_M,
    max_location_age_s: float = DEFAULT_MAX_LOCATION_AGE_S,
    exclude_driver_ids: Collection[uuid.UUID] = (),
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    raise NotImplementedError
