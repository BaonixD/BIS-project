from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from taxi_service.modules.rides.tariffs import TARIFFS, Tariff

TARIFF_VERSION: Final = "edu-v2"
CURRENCY: Final = "KZT"


@dataclass(frozen=True, slots=True)
class TariffRates:
    base_kzt: Decimal
    per_km_kzt: Decimal
    per_minute_kzt: Decimal
    minimum_kzt: Decimal


def _rates(base: int, per_km: int, per_minute: int, minimum: int) -> TariffRates:
    return TariffRates(Decimal(base), Decimal(per_km), Decimal(per_minute), Decimal(minimum))


RATES: Final[Mapping[Tariff, TariffRates]] = {
    Tariff.ECONOMY: _rates(500, 120, 20, 800),
    Tariff.COMFORT: _rates(700, 160, 25, 1100),
    Tariff.COMFORT_PLUS: _rates(900, 200, 30, 1500),
    Tariff.BUSINESS: _rates(1200, 260, 40, 2000),
}


@dataclass(frozen=True, slots=True)
class Fares:
    """The price of one route in every tariff, cheapest first."""

    amounts: Mapping[Tariff, int]
    currency: str = CURRENCY
    tariff_version: str = TARIFF_VERSION


def round_kzt(amount: Decimal) -> int:
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def calculate_fare(*, distance_m: int, duration_s: int, tariff: Tariff = Tariff.ECONOMY) -> int:
    """Tariff ``edu-v2`` for road-route metrics in metres and seconds, in whole tenge."""
    _require_metric("distance_m", distance_m)
    _require_metric("duration_s", duration_s)
    rates = RATES[tariff]
    raw = (
        rates.base_kzt
        + rates.per_km_kzt * Decimal(distance_m) / 1000
        + rates.per_minute_kzt * Decimal(duration_s) / 60
    )
    return round_kzt(max(rates.minimum_kzt, raw))


def calculate_fares(*, distance_m: int, duration_s: int) -> Fares:
    return Fares(
        amounts={
            tariff: calculate_fare(distance_m=distance_m, duration_s=duration_s, tariff=tariff)
            for tariff in TARIFFS
        }
    )


def _require_metric(name: str, value: int) -> None:
    # bool is an int subclass, so the exact type is checked.
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
