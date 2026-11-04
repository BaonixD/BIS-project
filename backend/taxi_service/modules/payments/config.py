import re
from typing import Final
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KASPI_PAYMENT_HOST: Final = "pay.kaspi.kz"
_PAYMENT_PATH: Final = re.compile(r"/pay/[A-Za-z0-9_-]{1,64}")


class InvalidKaspiPaymentUrlError(ValueError):
    """Configuration error; the message never repeats the configured value."""


def validate_kaspi_payment_url(raw: str) -> str:
    """The canonical ``https://pay.kaspi.kz/pay/<id>``; the POS link takes no amount."""
    value = raw.strip()
    if not value.isascii() or any(char.isspace() or not char.isprintable() for char in value):
        raise _invalid("must be a single ASCII URL without spaces or control characters")
    try:
        parts = urlsplit(value)
    except ValueError:
        raise _invalid("is not a parsable URL") from None
    if parts.scheme != "https":
        raise _invalid("must use https")
    if parts.netloc != KASPI_PAYMENT_HOST:
        raise _invalid(f"host must be exactly {KASPI_PAYMENT_HOST}, without credentials or port")
    if parts.query or parts.fragment or not _PAYMENT_PATH.fullmatch(parts.path):
        raise _invalid("path must be /pay/<id> without query or fragment")
    return f"https://{KASPI_PAYMENT_HOST}{parts.path}"


def _invalid(reason: str) -> InvalidKaspiPaymentUrlError:
    return InvalidKaspiPaymentUrlError(f"KASPI_PAYMENT_URL {reason}.")


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
