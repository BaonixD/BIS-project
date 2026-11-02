import math
from typing import Any

import pytest
from pydantic import ValidationError

from taxi_service.modules.geo.schemas import Coordinates, RouteGeometry, RouteResult

ABAY_DOSTYK = {"longitude": 76.9572, "latitude": 43.2389}
AL_FARABI = {"longitude": 76.9286, "latitude": 43.2187}
LINE = {"type": "LineString", "coordinates": [[76.9572, 43.2389], [76.9286, 43.2187]]}


def test_coordinates_accept_almaty_point_and_expose_lon_lat_order() -> None:
    point = Coordinates.model_validate(ABAY_DOSTYK)

    assert point.as_lon_lat() == (76.9572, 43.2389)


@pytest.mark.parametrize(
    "point",
    [
        {"longitude": -180, "latitude": -90},
        {"longitude": 180, "latitude": 90},
        {"longitude": 0, "latitude": 0},
    ],
)
def test_coordinates_accept_inclusive_bounds_and_integers(point: dict[str, Any]) -> None:
    assert Coordinates.model_validate(point).longitude == point["longitude"]


@pytest.mark.parametrize(
    "point",
    [
        {"longitude": 180.0001, "latitude": 43.2},
        {"longitude": -180.0001, "latitude": 43.2},
        {"longitude": 76.9, "latitude": 90.0001},
        {"longitude": 76.9, "latitude": -90.0001},
        {"longitude": math.nan, "latitude": 43.2},
        {"longitude": 76.9, "latitude": math.inf},
        {"longitude": True, "latitude": 43.2},
        {"longitude": "76.9", "latitude": 43.2},
        {"longitude": 76.9},
    ],
)
def test_coordinates_reject_out_of_range_or_non_numeric(point: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Coordinates.model_validate(point)


def test_route_geometry_is_a_geojson_linestring_of_lon_lat_positions() -> None:
    geometry = RouteGeometry.model_validate(LINE)

    assert geometry.model_dump(mode="json") == LINE


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [76.9, 43.2]},
        {"type": "LineString", "coordinates": [[76.9, 43.2]]},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[76.9, 43.2], [76.9]]},
        {"type": "LineString", "coordinates": [[76.9, 43.2], [76.9, 43.2, 900.0]]},
        {"type": "LineString", "coordinates": [[76.9, 43.2], [43.2, 176.9]]},
        {"type": "LineString", "coordinates": [[76.9, 43.2], ["76.9", 43.2]]},
        {"type": "LineString"},
    ],
)
def test_route_geometry_rejects_invalid_shapes(geometry: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RouteGeometry.model_validate(geometry)


def _route(**overrides: Any) -> dict[str, Any]:
    return {
        "distance_m": 4_120,
        "duration_s": 610,
        "route_geometry": LINE,
        "provider": "openrouteservice",
    } | overrides


def test_route_result_serializes_spec_shape() -> None:
    route = RouteResult.model_validate(_route())

    assert route.model_dump(mode="json") == _route()


@pytest.mark.parametrize(
    "overrides",
    [
        {"distance_m": -1},
        {"duration_s": -1},
        {"distance_m": 4_120.5},
        {"duration_s": True},
        {"distance_m": "4120"},
        {"provider": ""},
    ],
)
def test_route_result_rejects_invalid_metrics(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RouteResult.model_validate(_route(**overrides))
