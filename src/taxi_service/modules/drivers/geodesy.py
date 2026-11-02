"""Great-circle distance in metres and a bounding box for the SQL prefilter (ADR 0001)."""

from dataclasses import dataclass

from taxi_service.modules.geo.schemas import Coordinates

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min_latitude: float
    max_latitude: float
    longitude_ranges: tuple[tuple[float, float], ...]


def haversine_m(a: Coordinates, b: Coordinates) -> float:
    raise NotImplementedError


def bounding_box(center: Coordinates, radius_m: float) -> BoundingBox:
    raise NotImplementedError
