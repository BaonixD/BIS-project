import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taxi_service.modules.rides.schemas import RideSummary
from taxi_service.modules.users.models import UserRole


class AdminUserResponse(BaseModel):
    """An account in the admin list; ``display_name`` is null without a profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    created_at: datetime
    display_name: str | None
    blocked_at: datetime | None
    block_reason: str | None


class AccountAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    blocked: bool
    reason: str | None = Field(default=None, min_length=3, max_length=500)

    @model_validator(mode="after")
    def require_reason(self) -> "AccountAccessUpdate":
        if self.blocked and self.reason is None:
            raise ValueError("A block reason is required.")
        return self


class AdminOverview(BaseModel):
    total_users: int
    blocked_users: int
    pending_drivers: int
    online_drivers: int
    active_rides: int
    completed_rides: int
    cancelled_rides: int
    collected_kzt: int
    outstanding_cash_kzt: int


class AdminRideSummary(RideSummary):
    passenger_name: str
    driver_name: str | None
