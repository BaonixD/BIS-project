from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RoutingSettings(BaseSettings):
    """Road routing provider settings read from ``ROUTING_*`` variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="ROUTING_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    api_key: SecretStr | None = None
    base_url: HttpUrl = HttpUrl("https://api.openrouteservice.org")
    connect_timeout_s: float = Field(default=3.0, gt=0, le=30)
    read_timeout_s: float = Field(default=5.0, gt=0, le=60)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_s: float = Field(default=0.5, ge=0, le=10)
    max_retry_delay_s: float = Field(default=5.0, ge=0, le=30)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value
