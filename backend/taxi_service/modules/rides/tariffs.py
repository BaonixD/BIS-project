"""Tariffs from cheapest to dearest; a car class uses the same values (ADR 0012)."""

from enum import StrEnum
from typing import Final


class Tariff(StrEnum):
    ECONOMY = "economy"
    COMFORT = "comfort"
    COMFORT_PLUS = "comfort_plus"
    BUSINESS = "business"


TARIFFS: Final = tuple(Tariff)
TARIFF_MAX_LENGTH: Final = 16


def car_classes_for(tariff: Tariff) -> list[Tariff]:
    """Car classes that may serve ``tariff``: its own and every higher one."""
    return list(TARIFFS[TARIFFS.index(tariff) :])


def tariffs_above(car_class: Tariff) -> list[Tariff]:
    """Tariffs a car of ``car_class`` may not serve."""
    return list(TARIFFS[TARIFFS.index(car_class) + 1 :])


def tariff_check(column: str) -> str:
    """SQL of a CHECK constraint that ``column`` holds a tariff."""
    return f"{column} IN ({', '.join(f"'{tariff.value}'" for tariff in sorted(Tariff))})"


def categories_through(car_class: Tariff) -> list[Tariff]:
    """Legacy class eligibility, preserved when migrating or accepting an old client."""
    return list(TARIFFS[: TARIFFS.index(car_class) + 1])
