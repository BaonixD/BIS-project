"""Haversine distance in metres and the bounding box of a search circle."""

import math

import pytest

from taxi_service.modules.drivers.geodesy import EARTH_RADIUS_M, bounding_box, haversine_m
from taxi_service.modules.geo.schemas import Coordinates

ONE_DEGREE_M = EARTH_RADIUS_M * math.pi / 180  # about 111 195 m
ABAY_DOSTYK = Coordinates(longitude=76.9572, latitude=43.2389)
AL_FARABI = Coordinates(longitude=76.9286, latitude=43.2187)


def point(longitude: float, latitude: float) -> Coordinates:
    return Coordinates(longitude=longitude, latitude=latitude)


def test_distance_to_the_same_point_is_zero() -> None:
    assert haversine_m(ABAY_DOSTYK, ABAY_DOSTYK) == 0


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (point(76.9, 43.0), point(76.9, 44.0), ONE_DEGREE_M),
        (point(0, 0), point(1, 0), ONE_DEGREE_M),
        (point(0, 60), point(1, 60), 55_597.01),  # meridians converge: cos(60) = 1/2
        (point(0, 0), point(180, 0), math.pi * EARTH_RADIUS_M),
        (point(0, 90), point(0, -90), math.pi * EARTH_RADIUS_M),
        (point(179.5, 0), point(-179.5, 0), ONE_DEGREE_M),
        (ABAY_DOSTYK, AL_FARABI, 3_227.13),  # spherical law of cosines
    ],
)
def test_distance_in_metres(a: Coordinates, b: Coordinates, expected: float) -> None:
    assert haversine_m(a, b) == pytest.approx(expected, rel=1e-4)


def test_distance_is_symmetric_and_uses_lon_lat_order() -> None:
    assert haversine_m(ABAY_DOSTYK, AL_FARABI) == haversine_m(AL_FARABI, ABAY_DOSTYK)
    swapped = point(ABAY_DOSTYK.latitude, ABAY_DOSTYK.longitude)
    assert haversine_m(ABAY_DOSTYK, swapped) > 1_000_000


def contains(box_center: Coordinates, radius_m: float, target: Coordinates) -> bool:
    box = bounding_box(box_center, radius_m)
    in_latitude = box.min_latitude <= target.latitude <= box.max_latitude
    return in_latitude and any(
        low <= target.longitude <= high for low, high in box.longitude_ranges
    )


@pytest.mark.parametrize(
    "target",
    [
        point(76.9457, 43.2383 + 5000 / ONE_DEGREE_M),  # due north at the radius
        point(76.9457, 43.2383 - 5000 / ONE_DEGREE_M),  # due south
        point(76.9457 + 5000 / (ONE_DEGREE_M * math.cos(math.radians(43.2383))), 43.2383),
        point(76.9457 - 5000 / (ONE_DEGREE_M * math.cos(math.radians(43.2383))), 43.2383),
    ],
)
def test_box_contains_points_on_the_circle(target: Coordinates) -> None:
    center = point(76.9457, 43.2383)
    assert haversine_m(center, target) == pytest.approx(5000, abs=0.01)

    assert contains(center, 5000, target)


def test_box_is_tight_around_almaty() -> None:
    box = bounding_box(point(76.9457, 43.2383), 5000)

    assert box.max_latitude - box.min_latitude == pytest.approx(2 * 5000 / ONE_DEGREE_M, rel=1e-6)
    [(low, high)] = box.longitude_ranges
    assert 0.12 < high - low < 0.125  # 2 x 5 km at cos(43.24 deg)
    # 77.01 is 0.0643 deg east of the centre; the half-width is about 0.0617 deg.
    assert not contains(point(76.9457, 43.2383), 5000, point(77.01, 43.2383))


def test_box_crossing_the_antimeridian_is_split() -> None:
    box = bounding_box(point(179.99, 0), 5000)

    assert len(box.longitude_ranges) == 2
    assert contains(point(179.99, 0), 5000, point(-179.99, 0))
    assert not contains(point(179.99, 0), 5000, point(0, 0))


def test_box_around_a_pole_covers_every_longitude() -> None:
    box = bounding_box(point(10, 89.99), 5000)

    assert box.max_latitude == 90
    assert box.longitude_ranges == ((-180.0, 180.0),)
