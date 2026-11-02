from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.users.schemas import (
    PASSWORD_MAX_LENGTH,
    NewPassword,
    Username,
    UserResponse,
)


class RegisterRequest(BaseModel):
    username: Username
    password: NewPassword
    role: Literal["passenger", "driver"] = Field(
        description="Public registration creates passengers or drivers only; "
        "role 'admin' is rejected with 422 (admins are created by scripts/create_admin.py)."
    )


class LoginRequest(BaseModel):
    # Loose limits on purpose: format details must not tell which accounts exist.
    username: str = Field(min_length=1, max_length=64, examples=["alice_01"])
    password: SecretStr = Field(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, examples=["correct-horse-battery"]
    )


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str = Field(
        description="Send it as the X-CSRF-Token header with every POST/PUT/PATCH/DELETE "
        "made with this session. Valid until logout or expiry."
    )
    expires_at: datetime = Field(description="Server time (UTC) when the session ends.")

    @classmethod
    def from_user(cls, user: AuthenticatedUser) -> "SessionResponse":
        return cls(
            user=UserResponse.model_validate(user),
            csrf_token=user.csrf_token,
            expires_at=user.session_expires_at,
        )
