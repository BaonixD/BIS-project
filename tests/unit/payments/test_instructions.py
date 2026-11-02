from dataclasses import astuple
from decimal import Decimal
from uuid import UUID

import pytest

from taxi_service.modules.payments.config import PaymentSettings
from taxi_service.modules.payments.instructions import (
    PaymentInstructions,
    build_payment_instructions,
)
from taxi_service.modules.payments.rules import (
    PaymentMethod,
    PaymentState,
    PaymentStatus,
    Verification,
)

TEST_URL = "https://pay.kaspi.kz/pay/test123"
RIDE_ID = UUID("00000000-0000-4000-8000-000000000123")
AMOUNT = 1530

CASH = PaymentMethod.CASH
KASPI = PaymentMethod.KASPI_LINK


@pytest.fixture(autouse=True)
def _isolate_payment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KASPI_PAYMENT_URL", raising=False)


def settings(*, kaspi: bool) -> PaymentSettings:
    return PaymentSettings(_env_file=None, kaspi_payment_url=TEST_URL if kaspi else None)


def build(
    method: PaymentMethod, status: PaymentStatus, *, kaspi: bool, amount_kzt: int = AMOUNT
) -> PaymentInstructions:
    return build_payment_instructions(
        ride_id=RIDE_ID,
        amount_kzt=amount_kzt,
        state=PaymentState(method, status),
        settings=settings(kaspi=kaspi),
    )


def mentions_url(instructions: PaymentInstructions) -> bool:
    return any("kaspi.kz" in str(value) for value in astuple(instructions))


@pytest.mark.parametrize("kaspi", [True, False])
@pytest.mark.parametrize("status", list(PaymentStatus))
@pytest.mark.parametrize("method", list(PaymentMethod))
def test_common_fields_come_from_server_inputs(
    method: PaymentMethod, status: PaymentStatus, kaspi: bool
) -> None:
    instructions = build(method, status, kaspi=kaspi)

    assert instructions.ride_id == RIDE_ID
    assert instructions.amount_kzt == AMOUNT
    assert type(instructions.amount_kzt) is int
    assert instructions.currency == "KZT"
    assert instructions.method is method
    assert instructions.status is status
    assert instructions.verification is Verification.MANUAL
    assert instructions.kaspi_available is kaspi
    assert instructions.notice


@pytest.mark.parametrize("kaspi", [True, False])
@pytest.mark.parametrize("status", list(PaymentStatus))
def test_cash_never_contains_the_link(status: PaymentStatus, kaspi: bool) -> None:
    instructions = build(CASH, status, kaspi=kaspi)

    assert instructions.payment_url is None
    assert instructions.amount_entered_by_buyer is False
    assert not mentions_url(instructions)


@pytest.mark.parametrize("status", list(PaymentStatus))
def test_kaspi_without_configured_link_has_no_url(status: PaymentStatus) -> None:
    instructions = build(KASPI, status, kaspi=False)

    assert instructions.payment_url is None
    assert instructions.amount_entered_by_buyer is False
    assert not mentions_url(instructions)


@pytest.mark.parametrize("status", [PaymentStatus.UNPAID, PaymentStatus.REPORTED])
def test_open_kaspi_payment_gets_configured_link_and_manual_amount(status: PaymentStatus) -> None:
    instructions = build(KASPI, status, kaspi=True)

    assert instructions.payment_url == TEST_URL
    assert instructions.amount_entered_by_buyer is True
    assert f"{AMOUNT} KZT" in instructions.notice
    assert "does not confirm" in instructions.notice


def test_link_is_the_configured_one_and_carries_no_amount() -> None:
    instructions = build(KASPI, PaymentStatus.UNPAID, kaspi=True)

    assert instructions.payment_url == settings(kaspi=True).kaspi_payment_url
    assert str(AMOUNT) not in (instructions.payment_url or "")


def test_confirmed_kaspi_payment_hides_the_link() -> None:
    instructions = build(KASPI, PaymentStatus.CONFIRMED, kaspi=True)

    assert instructions.payment_url is None
    assert instructions.amount_entered_by_buyer is False
    assert "confirmed manually" in instructions.notice


def test_cash_notice_names_manual_confirmation() -> None:
    notice = build(CASH, PaymentStatus.UNPAID, kaspi=True).notice

    assert "cash" in notice
    assert "confirm" in notice


@pytest.mark.parametrize(
    "amount",
    [0, -1, True, 1530.0, Decimal(1530), "1530"],
    ids=["zero", "negative", "bool", "float", "decimal", "str"],
)
def test_amount_must_be_a_positive_int_from_the_ride_snapshot(amount: object) -> None:
    with pytest.raises(ValueError, match="amount_kzt"):
        build(CASH, PaymentStatus.UNPAID, kaspi=False, amount_kzt=amount)  # type: ignore[arg-type]
