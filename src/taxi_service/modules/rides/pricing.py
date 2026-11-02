from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

TARIFF_VERSION: Final = "edu-v1"
CURRENCY: Final = "KZT"

BASE_FARE_KZT: Final = Decimal(500)
PER_KM_KZT: Final = Decimal(120)
PER_MINUTE_KZT: Final = Decimal(20)
MINIMUM_FARE_KZT: Final = Decimal(800)


@dataclass(frozen=True, slots=True)
class Fare:
    amount_kzt: int
    currency: str = CURRENCY
    tariff_version: str = TARIFF_VERSION


def round_kzt(amount: Decimal) -> int:
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def calculate_fare(*, distance_m: int, duration_s: int) -> Fare:
    """Educational tariff ``edu-v1`` for road-route metrics in metres and seconds."""
    raw = (
        BASE_FARE_KZT
        + PER_KM_KZT * Decimal(distance_m) / 1000
        + PER_MINUTE_KZT * Decimal(duration_s) / 60
    )
    return Fare(amount_kzt=round_kzt(max(MINIMUM_FARE_KZT, raw)))
