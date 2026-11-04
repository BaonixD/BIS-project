import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from taxi_service.modules.users.models import UserRole


class AdminUserResponse(BaseModel):
    """An account in the admin list; ``display_name`` is null without a profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    created_at: datetime
    display_name: str | None
