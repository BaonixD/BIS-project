from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from taxi_service.modules.payments.kaspi import validate_kaspi_payment_url


class PaymentSettings(BaseSettings):
    """A blank ``KASPI_PAYMENT_URL`` disables Kaspi; an invalid one fails without echoing it."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    kaspi_payment_url: str | None = None

    @field_validator("kaspi_payment_url", mode="before")
    @classmethod
    def validate_link(cls, value: object) -> object:
        if isinstance(value, str):
            return validate_kaspi_payment_url(value) if value.strip() else None
        return value

    @property
    def kaspi_enabled(self) -> bool:
        return self.kaspi_payment_url is not None
