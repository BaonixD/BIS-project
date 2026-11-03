import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taxi_service.database.base import Base, UtcDateTime
from taxi_service.modules.users.models import PHONE_MAX_LENGTH

FULL_NAME_MAX_LENGTH = 100
LICENSE_NUMBER_MAX_LENGTH = 20
VEHICLE_TEXT_MAX_LENGTH = 50
PLATE_NUMBER_MIN_LENGTH = 4
PLATE_NUMBER_MAX_LENGTH = 10
VEHICLE_MIN_YEAR = 1980
VEHICLE_MAX_YEAR_IN_DATABASE = 2100
LOCATION_INDEX_NAME = "ix_driver_profiles_longitude_latitude"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"


class DriverProfile(Base):
    """Driver data of a ``users`` row with role ``driver``; the primary key is the user id.

    The row appears on the driver's first write (profile, location, availability);
    until then the driver is an empty pending profile. Constraints keep the
    states consistent: approved rows name the admin and time, only approved
    drivers can be online, a location is either complete and in range or absent.
    The (longitude, latitude) index serves the bounding-box prefilter of the
    nearest-driver search (ADR 0001).
    """

    __tablename__ = "driver_profiles"
    __table_args__ = (
        CheckConstraint("approval_status IN ('pending', 'approved')", name="approval_status"),
        CheckConstraint(
            "(approval_status = 'approved' AND approved_at IS NOT NULL AND approved_by IS NOT NULL)"
            " OR (approval_status = 'pending' AND approved_at IS NULL AND approved_by IS NULL)",
            name="approval_recorded",
        ),
        CheckConstraint(
            "NOT is_online OR approval_status = 'approved'", name="online_requires_approval"
        ),
        CheckConstraint(
            "(longitude IS NULL AND latitude IS NULL AND location_updated_at IS NULL)"
            " OR (longitude IS NOT NULL AND latitude IS NOT NULL"
            " AND location_updated_at IS NOT NULL)",
            name="location_complete",
        ),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        Index(LOCATION_INDEX_NAME, "longitude", "latitude"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(String(FULL_NAME_MAX_LENGTH))
    phone: Mapped[str | None] = mapped_column(String(PHONE_MAX_LENGTH))
    license_number: Mapped[str | None] = mapped_column(String(LICENSE_NUMBER_MAX_LENGTH))
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(
            ApprovalStatus,
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda statuses: [status.value for status in statuses],
        )
    )
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    is_online: Mapped[bool] = mapped_column(Boolean())
    longitude: Mapped[float | None] = mapped_column(Float())
    latitude: Mapped[float | None] = mapped_column(Float())
    location_updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())

    vehicle: Mapped["Vehicle | None"] = relationship(lazy="joined", cascade="all, delete-orphan")

    @classmethod
    def new(cls, user_id: uuid.UUID, now: datetime) -> "DriverProfile":
        """Empty pending, offline profile without location or vehicle."""
        return cls(
            user_id=user_id,
            approval_status=ApprovalStatus.PENDING,
            is_online=False,
            created_at=now,
            updated_at=now,
            vehicle=None,
        )


class Vehicle(Base):
    """The single car of a driver; ``plate_number`` is stored normalized and is unique."""

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            "plate_number = upper(plate_number) AND length(plate_number) "
            f"BETWEEN {PLATE_NUMBER_MIN_LENGTH} AND {PLATE_NUMBER_MAX_LENGTH}",
            name="plate_number_normalized",
        ),
        CheckConstraint(
            f"year BETWEEN {VEHICLE_MIN_YEAR} AND {VEHICLE_MAX_YEAR_IN_DATABASE}", name="year_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.user_id", ondelete="CASCADE"), unique=True
    )
    make: Mapped[str] = mapped_column(String(VEHICLE_TEXT_MAX_LENGTH))
    model: Mapped[str] = mapped_column(String(VEHICLE_TEXT_MAX_LENGTH))
    color: Mapped[str] = mapped_column(String(VEHICLE_TEXT_MAX_LENGTH))
    plate_number: Mapped[str] = mapped_column(String(PLATE_NUMBER_MAX_LENGTH), unique=True)
    year: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())


def missing_fields(profile: DriverProfile | None) -> list[str]:
    """What the driver still has to fill in before approval, in a fixed order."""
    if profile is None:
        return ["full_name", "phone", "license_number", "vehicle"]
    values = {
        "full_name": profile.full_name,
        "phone": profile.phone,
        "license_number": profile.license_number,
        "vehicle": profile.vehicle,
    }
    return [name for name, value in values.items() if value is None]
