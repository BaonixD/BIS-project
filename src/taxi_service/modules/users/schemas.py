import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from taxi_service.modules.users.models import UserRole

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

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


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str = Field(description="As registered; login ignores case.")
    role: UserRole
    created_at: datetime
