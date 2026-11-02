from typing import Literal

from pydantic import BaseModel, Field

from taxi_service.modules.users.schemas import NewPassword, Username


class RegisterRequest(BaseModel):
    username: Username
    password: NewPassword
    role: Literal["passenger", "driver"] = Field(
        description="Public registration creates passengers or drivers only; "
        "role 'admin' is rejected with 422 (admins are created by scripts/create_admin.py)."
    )
