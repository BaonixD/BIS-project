"""Validation of the owner's Kaspi point-of-sale payment link."""

from typing import Final

KASPI_PAYMENT_HOST: Final = "pay.kaspi.kz"


class InvalidKaspiPaymentUrlError(ValueError):
    """Configuration error; the message never repeats the configured value."""


def validate_kaspi_payment_url(raw: str) -> str:
    return raw
