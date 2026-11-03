from typing import Annotated, Literal

from fastapi import Depends, Request
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from taxi_service.core.origins import normalize_origin

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation errors must not echo values such as a URL with a password.
        hide_input_in_errors=True,
    )

    log_level: LogLevel = "INFO"
    database_url: str = Field(repr=False)

    session_cookie_secure: bool = True
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    password_hash_time_cost: int = Field(default=3, ge=1)
    password_hash_memory_kib: int = Field(default=65536, ge=8)
    password_hash_parallelism: int = Field(default=4, ge=1)

    login_max_attempts: int = Field(default=5, ge=1)
    login_attempt_window_seconds: int = Field(default=900, ge=1)
    login_limiter_max_keys: int = Field(default=10_000, ge=1)

    google_client_id: str | None = None

    offer_ttl_s: int = Field(default=30, ge=1)
    search_budget_s: int = Field(default=180, ge=1)
    dispatch_interval_s: float = Field(default=1.0, gt=0)
    dispatch_loop_enabled: bool = True

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            make_url(value)
        except ArgumentError:
            # The message must not echo the value back.
            raise ValueError("must be a SQLAlchemy database URL") from None
        return value

    @field_validator("google_client_id")
    @classmethod
    def blank_client_id_means_off(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def normalize_origins(cls, value: list[str]) -> list[str]:
        # Credentialed CORS must never be combined with a wildcard origin.
        return list(dict.fromkeys(normalize_origin(origin) for origin in value))


def get_settings(request: Request) -> Settings:
    """FastAPI dependency: the settings the application was created with."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
