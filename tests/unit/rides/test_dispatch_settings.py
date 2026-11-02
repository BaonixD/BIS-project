"""Dispatch settings: 30-second offers, 180-second search, a loop every second (MVP_SPEC §6)."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from taxi_service.core.config import Settings
from taxi_service.modules.rides.policy import DispatchPolicy

DATABASE_URL = "sqlite+aiosqlite:///./unit-test.db"
DISPATCH_VARIABLES = (
    "OFFER_TTL_S",
    "SEARCH_BUDGET_S",
    "DISPATCH_INTERVAL_S",
    "DISPATCH_LOOP_ENABLED",
)


@pytest.fixture(autouse=True)
def _no_dispatch_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in DISPATCH_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    settings = Settings(_env_file=None, database_url=DATABASE_URL)

    assert (
        settings.offer_ttl_s,
        settings.search_budget_s,
        settings.dispatch_interval_s,
        settings.dispatch_loop_enabled,
    ) == (30, 180, 1.0, True)


def test_values_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OFFER_TTL_S", "20")
    monkeypatch.setenv("SEARCH_BUDGET_S", "120")
    monkeypatch.setenv("DISPATCH_INTERVAL_S", "0.5")
    monkeypatch.setenv("DISPATCH_LOOP_ENABLED", "false")

    settings = Settings(_env_file=None, database_url=DATABASE_URL)

    assert (
        settings.offer_ttl_s,
        settings.search_budget_s,
        settings.dispatch_interval_s,
        settings.dispatch_loop_enabled,
    ) == (20, 120, 0.5, False)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("offer_ttl_s", 0),
        ("search_budget_s", 0),
        ("dispatch_interval_s", 0),
        ("dispatch_interval_s", -1),
    ],
)
def test_non_positive_values_are_rejected(name: str, value: float) -> None:
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None, database_url=DATABASE_URL, **{name: value})  # type: ignore[arg-type]


def test_policy_from_settings() -> None:
    settings = Settings(
        _env_file=None, database_url=DATABASE_URL, offer_ttl_s=20, search_budget_s=90
    )

    policy = DispatchPolicy.from_settings(settings)

    assert (policy.offer_ttl, policy.search_budget) == (
        timedelta(seconds=20),
        timedelta(seconds=90),
    )
    assert (policy.radius_m, policy.max_location_age_s) == (5000.0, 60.0)
