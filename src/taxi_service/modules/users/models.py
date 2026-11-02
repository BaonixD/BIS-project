import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime

USERNAME_MAX_LENGTH = 32


class UserRole(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class User(Base):
    """Account with a local password; ``username`` keeps the spelling as registered."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH))
    username_normalized: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH))
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
