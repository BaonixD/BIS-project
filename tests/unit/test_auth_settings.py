"""Security settings: secure defaults, explicit opt-out for local HTTP, CORS allowlist."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from taxi_service.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = "sqlite+aiosqlite:///./unit-test.db"
SECURITY_VARIABLES = (
    "SESSION_COOKIE_SECURE",
    "CORS_ALLOWED_ORIGINS",
    "PASSWORD_HASH_TIME_COST",
    "PASSWORD_HASH_MEMORY_KIB",
    "PASSWORD_HASH_PARALLELISM",
    "LOGIN_MAX_ATTEMPTS",
    "LOGIN_ATTEMPT_WINDOW_SECONDS",
    "LOGIN_LIMITER_MAX_KEYS",
    "GOOGLE_CLIENT_ID",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECURITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def settings() -> Settings:
    return Settings(_env_file=None, database_url=DATABASE_URL)


def test_defaults_are_secure() -> None:
    defaults = settings()

    assert defaults.session_cookie_secure is True
    assert defaults.cors_allowed_origins == []
    # argon2-cffi RFC 9106 low-memory profile: Argon2id, t=3, 64 MiB, p=4.
    assert defaults.password_hash_time_cost == 3
    assert defaults.password_hash_memory_kib == 65536
    assert defaults.password_hash_parallelism == 4
    assert defaults.login_max_attempts == 5
    assert defaults.login_attempt_window_seconds == 900
    assert defaults.login_limiter_max_keys == 10_000


def test_secure_cookie_can_be_disabled_for_local_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")

    assert settings().session_cookie_secure is False


def test_cors_origins_are_read_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", " http://localhost:5173/ , HTTPS://Taxi.Example.kz:8443"
    )

    assert settings().cors_allowed_origins == [
        "http://localhost:5173",
        "https://taxi.example.kz:8443",
    ]


def test_empty_cors_variable_means_no_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")

    assert settings().cors_allowed_origins == []


@pytest.mark.parametrize(
    "origin",
    ["*", "null", "localhost:5173", "ftp://example.kz", "http://example.kz/app", "http://"],
)
def test_invalid_cors_origin_is_rejected(monkeypatch: pytest.MonkeyPatch, origin: str) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", f"http://localhost:5173,{origin}")

    with pytest.raises(ValidationError, match="cors_allowed_origins"):
        settings()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("PASSWORD_HASH_TIME_COST", "0"),
        ("PASSWORD_HASH_MEMORY_KIB", "4"),
        ("PASSWORD_HASH_PARALLELISM", "0"),
        ("LOGIN_MAX_ATTEMPTS", "0"),
        ("LOGIN_ATTEMPT_WINDOW_SECONDS", "0"),
        ("LOGIN_LIMITER_MAX_KEYS", "0"),
    ],
)
def test_out_of_range_security_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError, match=variable.lower()):
        settings()


def test_env_example_opts_into_local_http_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    example = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert example.session_cookie_secure is False
    assert example.cors_allowed_origins == ["http://localhost:5173"]
    assert example.google_client_id is None


def test_google_sign_in_is_off_without_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    assert settings().google_client_id is None
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "  ")
    assert settings().google_client_id is None


def test_google_client_id_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", " 1234-abc.apps.googleusercontent.com ")

    assert settings().google_client_id == "1234-abc.apps.googleusercontent.com"
