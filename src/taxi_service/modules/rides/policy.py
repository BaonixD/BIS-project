"""Timing and matching limits of the driver search (MVP_SPEC §6, ADR 0006)."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from taxi_service.core.config import Settings
from taxi_service.modules.drivers.candidates import (
    DEFAULT_MAX_LOCATION_AGE_S,
    DEFAULT_RADIUS_M,
)

DEFAULT_OFFER_TTL: Final = timedelta(seconds=30)
DEFAULT_SEARCH_BUDGET: Final = timedelta(seconds=180)


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchPolicy:
    """``offer_ttl`` per driver, ``search_budget`` per search, candidate radius and freshness."""

    offer_ttl: timedelta = DEFAULT_OFFER_TTL
    search_budget: timedelta = DEFAULT_SEARCH_BUDGET
    radius_m: float = DEFAULT_RADIUS_M
    max_location_age_s: float = DEFAULT_MAX_LOCATION_AGE_S

    def __post_init__(self) -> None:
        if self.offer_ttl <= timedelta(0) or self.search_budget <= timedelta(0):
            raise ValueError("offer_ttl and search_budget must be positive")

    @classmethod
    def from_settings(cls, settings: Settings) -> "DispatchPolicy":
        return cls(
            offer_ttl=timedelta(seconds=settings.offer_ttl_s),
            search_budget=timedelta(seconds=settings.search_budget_s),
        )


DEFAULT_DISPATCH_POLICY: Final = DispatchPolicy()
