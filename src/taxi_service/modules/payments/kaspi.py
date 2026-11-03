"""The POS link has no amount or callback parameters, so none are accepted."""

import re
from typing import Final
from urllib.parse import urlsplit

KASPI_PAYMENT_HOST: Final = "pay.kaspi.kz"
_PAYMENT_PATH: Final = re.compile(r"/pay/[A-Za-z0-9_-]{1,64}")


class InvalidKaspiPaymentUrlError(ValueError):
    """Configuration error; the message never repeats the configured value."""


def validate_kaspi_payment_url(raw: str) -> str:
    """Return the canonical link or raise for anything but ``https://pay.kaspi.kz/pay/<id>``."""
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
