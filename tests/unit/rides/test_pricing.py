from decimal import Decimal

import pytest

from taxi_service.modules.rides.pricing import (
    CURRENCY,
    TARIFF_VERSION,
    Fare,
    calculate_fare,
    round_kzt,
)


def test_reference_route_costs_2200_kzt() -> None:
    fare = calculate_fare(distance_m=10_000, duration_s=1_500)

    assert fare == Fare(amount_kzt=2200, currency="KZT", tariff_version="edu-v1")


def test_fare_carries_tariff_version_and_currency() -> None:
    fare = calculate_fare(distance_m=10_000, duration_s=1_500)

    assert fare.tariff_version == TARIFF_VERSION == "edu-v1"
    assert fare.currency == CURRENCY == "KZT"


@pytest.mark.parametrize(
    ("distance_m", "duration_s"),
    [(0, 0), (1_000, 60), (2_000, 120), (2_500, 0)],
)
def test_short_routes_cost_the_minimum_fare(distance_m: int, duration_s: int) -> None:
    assert calculate_fare(distance_m=distance_m, duration_s=duration_s).amount_kzt == 800


def test_fare_just_above_minimum_is_not_clamped() -> None:
    # 500 + 120 * 2.5 + 20 * 0.05 = 801
    assert calculate_fare(distance_m=2_500, duration_s=3).amount_kzt == 801


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
    assert calculate_fare(distance_m=distance_m, duration_s=duration_s).amount_kzt == expected


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
        calculate_fare(distance_m=distance_m, duration_s=duration_s)


@pytest.mark.parametrize(
    "value",
    [True, False, 1.5, 10_000.0, Decimal(10_000), "10000", None],
)
def test_non_integer_metrics_are_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        calculate_fare(distance_m=value, duration_s=1_500)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="integer"):
        calculate_fare(distance_m=10_000, duration_s=value)  # type: ignore[arg-type]
