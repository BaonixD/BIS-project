from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RoutingProviderName = Literal["osrm", "openrouteservice"]


class RoutingSettings(BaseSettings):
    """Road routing settings read from ``ROUTING_*``, ``OSRM_BASE_URL`` and ``.env``.

    ``api_key`` and ``base_url`` belong to openrouteservice; ``osrm_base_url`` to OSRM.
    """

    model_config = SettingsConfigDict(
        env_prefix="ROUTING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    provider: RoutingProviderName = "osrm"
    osrm_base_url: HttpUrl | None = Field(
        default=HttpUrl("http://127.0.0.1:5001"), validation_alias="OSRM_BASE_URL"
    )
    api_key: SecretStr | None = None
    base_url: HttpUrl = HttpUrl("https://api.openrouteservice.org")
    connect_timeout_s: float = Field(default=3.0, gt=0, le=30)
    read_timeout_s: float = Field(default=5.0, gt=0, le=60)
    max_retries: int = Field(default=1, ge=0, le=5)
    retry_backoff_s: float = Field(default=0.5, ge=0, le=10)
    max_retry_delay_s: float = Field(default=5.0, ge=0, le=30)
    total_timeout_s: float = Field(default=10.0, gt=0, le=60)

    @field_validator("api_key", "osrm_base_url", mode="before")
    @classmethod
    def blank_means_unset(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value
