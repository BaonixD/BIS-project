import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from taxi_service.modules.drivers.models import (
    FULL_NAME_MAX_LENGTH,
    LICENSE_NUMBER_MAX_LENGTH,
    PLATE_NUMBER_MAX_LENGTH,
    PLATE_NUMBER_MIN_LENGTH,
    VEHICLE_MAX_YEAR_IN_DATABASE,
    VEHICLE_MIN_YEAR,
    VEHICLE_TEXT_MAX_LENGTH,
    ApprovalStatus,
    DriverProfile,
    missing_fields,
)
from taxi_service.modules.geo.schemas import Coordinates
from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.ratings.schemas import RatingSummaryResponse
from taxi_service.modules.rides.tariffs import TARIFFS, Tariff
from taxi_service.modules.users.models import User
from taxi_service.modules.users.schemas import Phone
from taxi_service.schemas.patch import PatchRequest

_CODE_SEPARATORS = re.compile(r"[\s-]")


def _normalize_code(value: Any) -> Any:
    """Upper case without spaces or '-': '123 abc-02' -> '123ABC02'."""
    return _CODE_SEPARATORS.sub("", value).upper() if isinstance(value, str) else value


def _text(max_length: int, min_length: int = 1) -> Any:
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


FullName = Annotated[str, _text(FULL_NAME_MAX_LENGTH, 2), Field(examples=["Dana Driver"])]
LicenseNumber = Annotated[
    str,
    BeforeValidator(_normalize_code),
    Field(
        pattern=rf"^[A-Z0-9]{{5,{LICENSE_NUMBER_MAX_LENGTH}}}$",
        description="Driving licence number; stored upper case without spaces or '-'.",
        examples=["KZ1234567"],
    ),
]
PlateNumber = Annotated[
    str,
    BeforeValidator(_normalize_code),
    Field(
        pattern=rf"^[A-Z0-9]{{{PLATE_NUMBER_MIN_LENGTH},{PLATE_NUMBER_MAX_LENGTH}}}$",
        description="Unique across drivers; '123 abc-02' is stored as '123ABC02'.",
        examples=["123ABC02"],
    ),
]
VehicleText = Annotated[str, _text(VEHICLE_TEXT_MAX_LENGTH)]


class VehicleInput(BaseModel):
    """The driver's one car; sending it replaces all of its fields."""

    model_config = ConfigDict(extra="forbid")

    make: VehicleText = Field(examples=["Toyota"])
    model: VehicleText = Field(examples=["Camry"])
    color: VehicleText = Field(examples=["white"])
    plate_number: PlateNumber
    year: int = Field(
        strict=True,
        ge=VEHICLE_MIN_YEAR,
        le=VEHICLE_MAX_YEAR_IN_DATABASE,
        description=f"Model year from {VEHICLE_MIN_YEAR} to next year.",
        examples=[2020],
    )


class DriverProfileUpdate(PatchRequest):
    """Changing the name, licence or vehicle of an approved driver returns them to pending."""

    full_name: FullName | None = None
    phone: Phone | None = None
    license_number: LicenseNumber | None = None
    vehicle: VehicleInput | None = None


class AvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    online: bool = Field(strict=True)
    categories: list[Tariff] | None = Field(default=None, min_length=1, max_length=4)

    @field_validator("categories", mode="before")
    @classmethod
    def categories_not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("Omit categories to keep the previous selection.")
        return value

    @field_validator("categories")
    @classmethod
    def unique_categories(cls, value: list[Tariff] | None) -> list[Tariff] | None:
        if value is None:
            return None
        if len(set(value)) != len(value):
            raise ValueError("Categories must be unique.")
        return [tariff for tariff in TARIFFS if tariff in value]

    @model_validator(mode="after")
    def categories_only_online(self) -> "AvailabilityUpdate":
        if not self.online and self.categories is not None:
            raise ValueError("Categories are selected when going online.")
        return self


class LocationUpdate(Coordinates):
    """Current position; the time of the update is the server's, not the client's."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    make: str
    model: str
    color: str
    plate_number: str
    year: int
    car_class: Tariff = Field(description="Maximum car class, set by an admin.")
    categories: list[Tariff] = Field(
        min_length=1,
        max_length=4,
        description="All tariffs permitted by the maximum vehicle class.",
    )


class ApprovalRequest(PatchRequest):
    """Optional body of an approval; without ``car_class`` the class stays as it is."""

    car_class: Tariff | None = None


class CarClassUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    car_class: Tariff


class DriverResponse(BaseModel):
    """A driver's profile, vehicle, approval, availability and current location."""

    id: uuid.UUID
    full_name: str | None
    phone: str | None
    license_number: str | None
    vehicle: VehicleResponse | None
    approval_status: ApprovalStatus
    approved_at: datetime | None
    online: bool
    enabled_categories: list[Tariff] = Field(description="Working tariffs selected by the driver.")
    location: Coordinates | None
    location_updated_at: datetime | None = Field(description="Server time of the last location.")
    missing_fields: list[str] = Field(
        description="Fields still needed before approval; empty when complete."
    )
    rating: RatingSummaryResponse = Field(description="Stars the driver received from passengers.")

    @classmethod
    def build(
        cls, user_id: uuid.UUID, profile: DriverProfile | None, rating: RatingSummary
    ) -> "DriverResponse":
        return cls(**_driver_fields(user_id, profile), rating=RatingSummaryResponse.build(rating))


class AdminDriverResponse(DriverResponse):
    blocked_at: datetime | None
    username: str
    created_at: datetime = Field(description="Registration time of the account.")
    approved_by: uuid.UUID | None

    @classmethod
    def from_rows(
        cls, user: User, profile: DriverProfile | None, rating: RatingSummary
    ) -> "AdminDriverResponse":
        return cls(
            **_driver_fields(user.id, profile),
            rating=RatingSummaryResponse.build(rating),
            blocked_at=user.blocked_at,
            username=user.username,
            created_at=user.created_at,
            approved_by=profile.approved_by if profile else None,
        )


def _driver_fields(user_id: uuid.UUID, profile: DriverProfile | None) -> dict[str, Any]:
    if profile is None:
        return {
            "id": user_id,
            "full_name": None,
            "phone": None,
            "license_number": None,
            "vehicle": None,
            "approval_status": ApprovalStatus.PENDING,
            "approved_at": None,
            "online": False,
            "enabled_categories": [],
            "location": None,
            "location_updated_at": None,
            "missing_fields": missing_fields(None),
        }
    location = None
    if profile.longitude is not None and profile.latitude is not None:
        location = Coordinates(longitude=profile.longitude, latitude=profile.latitude)
    return {
        "id": user_id,
        "full_name": profile.full_name,
        "phone": profile.phone,
        "license_number": profile.license_number,
        "vehicle": VehicleResponse.model_validate(profile.vehicle) if profile.vehicle else None,
        "approval_status": profile.approval_status,
        "approved_at": profile.approved_at,
        "online": profile.is_online,
        "enabled_categories": profile.vehicle.enabled_categories if profile.vehicle else [],
        "location": location,
        "location_updated_at": profile.location_updated_at,
        "missing_fields": missing_fields(profile),
    }
