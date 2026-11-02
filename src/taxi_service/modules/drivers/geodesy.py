"""Great-circle distance in metres and a bounding box for the SQL prefilter (ADR 0001).

The Earth is a sphere with the mean radius here: within a 5 km search the
error against the WGS 84 ellipsoid is well below a metre per kilometre and
the same for every candidate, so the nearest-first order is unaffected.
"""

import math
from dataclasses import dataclass

from taxi_service.modules.geo.schemas import Coordinates

EARTH_RADIUS_M = 6_371_008.8
# Widens the box against rounding; the exact radius check happens afterwards.
_BOX_MARGIN_DEG = 1e-9


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Latitude range and one or two longitude ranges (two across the antimeridian)."""

    min_latitude: float
    max_latitude: float
    longitude_ranges: tuple[tuple[float, float], ...]


def haversine_m(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance between two points in metres."""
    lat_a, lat_b = math.radians(a.latitude), math.radians(b.latitude)
    half_dlat = (lat_b - lat_a) / 2
    half_dlon = math.radians(b.longitude - a.longitude) / 2
    h = math.sin(half_dlat) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(half_dlon) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def bounding_box(center: Coordinates, radius_m: float) -> BoundingBox:
    """Smallest latitude/longitude box containing every point within ``radius_m``.

    Longitude half-width is ``asin(sin(r) / cos(lat))`` (J. P. Matuschek,
    "Finding Points Within a Distance of a Latitude/Longitude Using Bounding
    Coordinates"); if the circle reaches a pole, every longitude is inside.
    """
    angular = radius_m / EARTH_RADIUS_M
    delta_lat = math.degrees(angular) + _BOX_MARGIN_DEG
    min_lat = center.latitude - delta_lat
    max_lat = center.latitude + delta_lat
    if min_lat <= -90 or max_lat >= 90 or angular >= math.pi / 2:
        return BoundingBox(max(min_lat, -90.0), min(max_lat, 90.0), ((-180.0, 180.0),))
    ratio = math.sin(angular) / math.cos(math.radians(center.latitude))
    delta_lon = math.degrees(math.asin(min(1.0, ratio))) + _BOX_MARGIN_DEG
    return BoundingBox(min_lat, max_lat, _longitude_ranges(center.longitude, delta_lon))


def _longitude_ranges(longitude: float, delta: float) -> tuple[tuple[float, float], ...]:
    low, high = longitude - delta, longitude + delta
    if low < -180:
        return ((low + 360, 180.0), (-180.0, high))
    if high > 180:
        return ((low, 180.0), (-180.0, high - 360))
    return ((low, high),)
