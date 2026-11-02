import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from taxi_service.modules.geo.config import RoutingSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SECRET = "eyJ-routing-secret-value"


@pytest.fixture(autouse=True)
def _isolate_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("ROUTING_"):
            monkeypatch.delenv(name)


def test_defaults_without_environment_have_no_key() -> None:
    settings = RoutingSettings(_env_file=None)

    assert settings.api_key is None
    assert str(settings.base_url) == "https://api.openrouteservice.org/"
    assert settings.max_retries == 2


def test_blank_key_from_env_example_means_not_configured() -> None:
    settings = RoutingSettings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.api_key is None


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_key_from_environment_means_not_configured(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("ROUTING_API_KEY", value)

    assert RoutingSettings(_env_file=None).api_key is None


@pytest.mark.parametrize("value", [f" {SECRET}\n", f"\t{SECRET}  "])
def test_key_surrounding_whitespace_is_stripped(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("ROUTING_API_KEY", value)

    settings = RoutingSettings(_env_file=None)

    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == SECRET


def test_key_is_read_from_prefixed_environment_and_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROUTING_API_KEY", SECRET)

    settings = RoutingSettings(_env_file=None)

    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == SECRET
    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)
    assert SECRET not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ROUTING_MAX_RETRIES", "-1"),
        ("ROUTING_MAX_RETRIES", "50"),
        ("ROUTING_READ_TIMEOUT_S", "0"),
        ("ROUTING_BASE_URL", "not a url"),
    ],
)
def test_unsafe_values_are_rejected(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        RoutingSettings(_env_file=None)
