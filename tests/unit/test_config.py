from pathlib import Path

import pytest
from pydantic import ValidationError

from taxi_service.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = "sqlite+aiosqlite:///./unit-test.db"


def test_defaults_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(_env_file=None, database_url=DATABASE_URL)

    assert settings.log_level == "INFO"


def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert Settings(_env_file=None, database_url=DATABASE_URL).log_level == "DEBUG"


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "verbose")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=DATABASE_URL)


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    assert Settings(_env_file=None).database_url == DATABASE_URL


def test_malformed_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None, database_url="not a database url")


def test_rejected_database_url_is_not_echoed_in_error(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_value = "not-a-url-with-s3cr3t-password"
    monkeypatch.setenv("DATABASE_URL", secret_value)

    with pytest.raises(ValidationError, match="database_url") as error:
        Settings(_env_file=None)

    assert secret_value not in str(error.value)


def test_database_url_is_hidden_from_repr() -> None:
    settings = Settings(_env_file=None, database_url=DATABASE_URL)

    assert DATABASE_URL not in repr(settings)


def test_env_example_is_loadable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite+aiosqlite:///./taxi.db"
