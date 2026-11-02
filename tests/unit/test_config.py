from pathlib import Path

import pytest
from pydantic import ValidationError

from taxi_service.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_defaults_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.log_level == "INFO"


def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert Settings(_env_file=None).log_level == "DEBUG"


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "verbose")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_env_example_is_loadable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.log_level == "INFO"
