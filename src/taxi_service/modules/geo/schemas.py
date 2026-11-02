from pydantic import BaseModel, ConfigDict


class Coordinates(BaseModel):
    model_config = ConfigDict(frozen=True)

    longitude: float
    latitude: float

    def as_lon_lat(self) -> tuple[float, float]:
        return (self.longitude, self.latitude)


class RouteGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    coordinates: tuple[tuple[float, ...], ...]


class RouteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    distance_m: int
    duration_s: int
    route_geometry: RouteGeometry
    provider: str
