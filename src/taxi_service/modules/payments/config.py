from pydantic_settings import BaseSettings, SettingsConfigDict


class PaymentSettings(BaseSettings):
    """Payment settings; ``KASPI_PAYMENT_URL`` keeps its unprefixed name from ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    kaspi_payment_url: str | None = None

    @property
    def kaspi_enabled(self) -> bool:
        return self.kaspi_payment_url is not None
