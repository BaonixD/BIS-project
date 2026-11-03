import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime

USERNAME_MAX_LENGTH = 32
DISPLAY_NAME_MAX_LENGTH = 64
PHONE_MAX_LENGTH = 16


class UserRole(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class User(Base):
    """Case-insensitive uniqueness through ``username_normalized``, enforced by the database."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username_normalized = lower(username)", name="username_normalized"),
        CheckConstraint("role IN ('passenger', 'driver', 'admin')", name="role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH))
    username_normalized: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda roles: [role.value for role in roles],
        )
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class UserProfile(Base):
    """Kept apart from ``users`` so role and password never share its update path."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            f"display_name IS NULL OR length(display_name) BETWEEN 1 AND {DISPLAY_NAME_MAX_LENGTH}",
            name="display_name_length",
        ),
        CheckConstraint(
            f"phone IS NULL OR (substr(phone, 1, 1) = '+' "
            f"AND length(phone) BETWEEN 11 AND {PHONE_MAX_LENGTH})",
            name="phone_format",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(DISPLAY_NAME_MAX_LENGTH))
    phone: Mapped[str | None] = mapped_column(String(PHONE_MAX_LENGTH))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
