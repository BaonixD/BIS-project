from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from taxi_service.modules.payments.kaspi import validate_kaspi_payment_url


class PaymentSettings(BaseSettings):
    """Payment settings; ``KASPI_PAYMENT_URL`` keeps its unprefixed name from ``.env``.

    A blank or missing link disables Kaspi while cash keeps working. An invalid
    link fails at load; the error does not repeat the configured value.
    """

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
