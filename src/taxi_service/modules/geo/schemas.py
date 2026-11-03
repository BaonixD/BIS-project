from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Longitude = Annotated[float, Field(strict=True, ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Field(strict=True, ge=-90, le=90, allow_inf_nan=False)]
Position = tuple[Longitude, Latitude]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class Coordinates(BaseModel):
    """WGS 84 point (SRID 4326); serialized as ``{longitude, latitude}``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    longitude: Longitude = Field(examples=[76.9572])
    latitude: Latitude = Field(examples=[43.2389])

    def as_lon_lat(self) -> Position:
        return (self.longitude, self.latitude)


class RouteRequest(BaseModel):
    """Two points of a road route, in driving order."""

    model_config = ConfigDict(extra="forbid")

    origin: Coordinates
    destination: Coordinates


class RouteGeometry(BaseModel):
    """GeoJSON LineString; every position is ``[longitude, latitude]``."""

    model_config = ConfigDict(frozen=True)

    type: Literal["LineString"]
    coordinates: tuple[Position, ...] = Field(min_length=2)


class RouteResult(BaseModel):
    """Road route normalized from an external provider."""

    model_config = ConfigDict(frozen=True)

    distance_m: NonNegativeInt
    duration_s: NonNegativeInt
    route_geometry: RouteGeometry
    provider: str = Field(min_length=1)
