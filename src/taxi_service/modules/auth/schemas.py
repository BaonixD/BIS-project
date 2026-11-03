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

# Google ID tokens are about 1-2 KB.
GOOGLE_CREDENTIAL_MAX_LENGTH = 4096


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


class GoogleLoginRequest(BaseModel):
    credential: SecretStr = Field(
        min_length=1,
        max_length=GOOGLE_CREDENTIAL_MAX_LENGTH,
        description="Google ID token (JWT) from Google Identity Services: "
        "the `credential` of the sign-in callback.",
    )


class AuthProvidersResponse(BaseModel):
    google_client_id: str | None = Field(
        description="OAuth client ID for Google Identity Services; null when "
        "sign-in with Google is off (hide the button)."
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
