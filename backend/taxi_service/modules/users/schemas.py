import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr, StringConstraints

from taxi_service.modules.ratings.records import RatingSummary
from taxi_service.modules.ratings.schemas import RatingSummaryResponse
from taxi_service.modules.users.models import (
    DISPLAY_NAME_MAX_LENGTH,
    LoginMethod,
    User,
    UserProfile,
    UserRole,
)
from taxi_service.schemas.patch import PatchRequest

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
PHONE_PATTERN = r"^\+[1-9][0-9]{9,14}$"
_PHONE_SEPARATORS = re.compile(r"[\s()-]")

Username = Annotated[
    str,
    Field(
        pattern=USERNAME_PATTERN,
        description="3-32 ASCII letters, digits or '_'; unique regardless of case.",
        examples=["alice_01"],
    ),
]
NewPassword = Annotated[
    SecretStr,
    Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="10-128 characters; stored only as an Argon2id hash.",
        examples=["correct-horse-battery"],
    ),
]


def _strip_phone_separators(value: Any) -> Any:
    return _PHONE_SEPARATORS.sub("", value) if isinstance(value, str) else value


Phone = Annotated[
    str,
    BeforeValidator(_strip_phone_separators),
    Field(
        pattern=PHONE_PATTERN,
        description="International format; spaces, '-' and brackets are removed: "
        "'+7 701 123-45-67' is stored as '+77011234567'.",
        examples=["+77011234567"],
    ),
]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH),
    Field(description="Name shown to other participants of a ride.", examples=["Alice"]),
]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str = Field(description="As registered; login ignores case.")
    role: UserRole
    created_at: datetime


class MyProfileResponse(UserResponse):
    """The caller's account and contact details; empty until set by PATCH."""

    display_name: str | None
    phone: str | None
    rating: RatingSummaryResponse = Field(
        description="Stars received from the other side of rides (count 0 for an admin)."
    )
    login_method: LoginMethod = Field(description="google for an account made by Google sign-in.")
    email: str | None = Field(description="The Google account's email; null for a password login.")

    @classmethod
    def build(
        cls, user: User, profile: UserProfile | None, rating: RatingSummary
    ) -> "MyProfileResponse":
        return cls(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
            display_name=profile.display_name if profile else None,
            phone=profile.phone if profile else None,
            rating=RatingSummaryResponse.build(rating),
            login_method=user.login_method,
            email=user.email,
        )


class MyProfileUpdate(PatchRequest):
    """Only these fields are writable; role, username and approval are not."""

    display_name: DisplayName | None = None
    phone: Phone | None = None
