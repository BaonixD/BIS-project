from decimal import Decimal

import pytest

from taxi_service.modules.rides.pricing import (
    CURRENCY,
    TARIFF_VERSION,
    calculate_fare,
    calculate_fares,
    round_kzt,
)
from taxi_service.modules.rides.tariffs import Tariff, car_classes_for, tariffs_above

REFERENCE_AMOUNTS = {
    Tariff.ECONOMY: 2200,
    Tariff.COMFORT: 2925,
    Tariff.COMFORT_PLUS: 3650,
    Tariff.BUSINESS: 4800,
}
MINIMUM_FARES = {
    Tariff.ECONOMY: 800,
    Tariff.COMFORT: 1100,
    Tariff.COMFORT_PLUS: 1500,
    Tariff.BUSINESS: 2000,
}


def test_tariffs_go_from_economy_to_business() -> None:
    assert [tariff.value for tariff in Tariff] == [
        "economy",
        "comfort",
        "comfort_plus",
        "business",
    ]


def test_reference_route_prices_every_tariff() -> None:
    fares = calculate_fares(distance_m=10_000, duration_s=1_500)

    assert fares.amounts == REFERENCE_AMOUNTS
    assert list(fares.amounts) == list(Tariff)
    assert (fares.currency, fares.tariff_version) == ("KZT", "edu-v2")


def test_fares_carry_tariff_version_and_currency() -> None:
    assert TARIFF_VERSION == "edu-v2"
    assert CURRENCY == "KZT"


@pytest.mark.parametrize(("tariff", "minimum"), MINIMUM_FARES.items())
@pytest.mark.parametrize(("distance_m", "duration_s"), [(0, 0), (1_000, 60), (2_000, 120)])
def test_short_routes_cost_the_minimum_fare(
    tariff: Tariff, minimum: int, distance_m: int, duration_s: int
) -> None:
    assert calculate_fare(distance_m=distance_m, duration_s=duration_s, tariff=tariff) == minimum


def test_fare_just_above_minimum_is_not_clamped() -> None:
    # 500 + 120 * 2.5 + 20 * 0.05 = 801
    assert calculate_fare(distance_m=2_500, duration_s=3) == 801
    # 1200 + 260 * 3 + 40 * 0.5 = 2000 is the minimum; one metre more is 2000.26 -> 2000
    assert calculate_fare(distance_m=3_001, duration_s=30, tariff=Tariff.BUSINESS) == 2000
    # 1200 + 260 * 3.002 + 40 * 0.5 = 2000.52 -> 2001
    assert calculate_fare(distance_m=3_002, duration_s=30, tariff=Tariff.BUSINESS) == 2001


@pytest.mark.parametrize(
    ("distance_m", "duration_s", "expected"),
    [
        # 500 + 602.16 + 0.333... = 1102.4933... -> down
        (5_018, 1, 1102),
        # 500 + 601.2 + 0.333... = 1101.5333... -> up
        (5_010, 1, 1102),
        # 500 + 602.52 = 1102.52 -> up
        (5_021, 0, 1103),
        # 500 + 0.12 + 1000.333... = 1500.4533... -> down
        (1, 3_001, 1500),
    ],
)
def test_fractional_amounts_round_to_nearest_tenge(
    distance_m: int, duration_s: int, expected: int
) -> None:
    assert calculate_fare(distance_m=distance_m, duration_s=duration_s) == expected


def test_half_tenge_of_a_higher_tariff_rounds_up() -> None:
    # 700 + 160 * 10 + 25 * 0.1 = 2302.5 -> 2303
    assert calculate_fare(distance_m=10_000, duration_s=6, tariff=Tariff.COMFORT) == 2303
    # 900 + 200 * 10 + 30 * 0.1 = 2903
    assert calculate_fare(distance_m=10_000, duration_s=6, tariff=Tariff.COMFORT_PLUS) == 2903


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("1100.5"), 1101),
        (Decimal("1101.5"), 1102),
        (Decimal("1100.4999"), 1100),
        (Decimal("2200"), 2200),
    ],
)
def test_exact_halves_round_up(amount: Decimal, expected: int) -> None:
    assert round_kzt(amount) == expected


@pytest.mark.parametrize(
    ("distance_m", "duration_s"),
    [(-1, 0), (0, -1), (-10_000, 1_500)],
)
def test_negative_metrics_are_rejected(distance_m: int, duration_s: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        calculate_fares(distance_m=distance_m, duration_s=duration_s)


@pytest.mark.parametrize(
    "value",
    [True, False, 1.5, 10_000.0, Decimal(10_000), "10000", None],
)
def test_non_integer_metrics_are_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        calculate_fares(distance_m=value, duration_s=1_500)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="integer"):
        calculate_fares(distance_m=10_000, duration_s=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tariff", "classes"),
    [
        (Tariff.ECONOMY, ["economy", "comfort", "comfort_plus", "business"]),
        (Tariff.COMFORT, ["comfort", "comfort_plus", "business"]),
        (Tariff.COMFORT_PLUS, ["comfort_plus", "business"]),
        (Tariff.BUSINESS, ["business"]),
    ],
)
def test_a_tariff_is_served_by_its_class_and_higher(tariff: Tariff, classes: list[str]) -> None:
    assert [car_class.value for car_class in car_classes_for(tariff)] == classes


@pytest.mark.parametrize(
    ("car_class", "above"),
    [
        (Tariff.ECONOMY, ["comfort", "comfort_plus", "business"]),
        (Tariff.COMFORT_PLUS, ["business"]),
        (Tariff.BUSINESS, []),
    ],
)
def test_tariffs_above_a_car_class(car_class: Tariff, above: list[str]) -> None:
    assert [tariff.value for tariff in tariffs_above(car_class)] == above
