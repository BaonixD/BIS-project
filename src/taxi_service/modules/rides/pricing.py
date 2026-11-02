from dataclasses import dataclass
from decimal import Decimal
from typing import Final

TARIFF_VERSION: Final = "edu-v1"
CURRENCY: Final = "KZT"


@dataclass(frozen=True, slots=True)
class Fare:
    amount_kzt: int
    currency: str = CURRENCY
    tariff_version: str = TARIFF_VERSION


def round_kzt(amount: Decimal) -> int:
    return int(amount)


def calculate_fare(*, distance_m: int, duration_s: int) -> Fare:
    return Fare(amount_kzt=0)
