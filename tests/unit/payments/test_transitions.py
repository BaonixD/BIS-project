import pytest

from taxi_service.modules.payments.exceptions import (
    InvalidPaymentTransitionError,
    KaspiUnavailableError,
)
from taxi_service.modules.payments.rules import (
    PaymentDecision,
    PaymentMethod,
    PaymentState,
    PaymentStatus,
    Verification,
    apply_confirm,
    apply_method_change,
    apply_report,
    initial_payment_state,
)

CASH = PaymentMethod.CASH
KASPI = PaymentMethod.KASPI_LINK
UNPAID = PaymentStatus.UNPAID
REPORTED = PaymentStatus.REPORTED
CONFIRMED = PaymentStatus.CONFIRMED

ALL_STATES = [PaymentState(method, status) for method in PaymentMethod for status in PaymentStatus]


def state_id(value: object) -> str | None:
    if isinstance(value, PaymentState):
        return f"{value.method}-{value.status}"
    return None


def test_wire_values_are_stable() -> None:
    assert [m.value for m in PaymentMethod] == ["cash", "kaspi_link"]
    assert [s.value for s in PaymentStatus] == ["unpaid", "reported", "confirmed"]
    assert [v.value for v in Verification] == ["manual"]


def test_new_payment_is_unpaid_cash() -> None:
    assert initial_payment_state() == PaymentState(CASH, UNPAID)


# --- report: the passenger's statement "I paid" -------------------------------------------

REPORT_ALLOWED = {
    PaymentState(KASPI, UNPAID): PaymentDecision(PaymentState(KASPI, REPORTED), changed=True),
    PaymentState(KASPI, REPORTED): PaymentDecision(PaymentState(KASPI, REPORTED), changed=False),
}


@pytest.mark.parametrize("state", ALL_STATES, ids=state_id)
def test_report_matrix(state: PaymentState) -> None:
    expected = REPORT_ALLOWED.get(state)
    if expected is None:
        with pytest.raises(InvalidPaymentTransitionError) as caught:
            apply_report(state)
        assert caught.value.status_code == 409
        assert caught.value.code == "invalid_payment_transition"
        assert caught.value.details == {
            "action": "report",
            "method": state.method.value,
            "status": state.status.value,
        }
    else:
        assert apply_report(state) == expected


def test_report_never_confirms() -> None:
    decision = apply_report(PaymentState(KASPI, UNPAID))

    assert decision.state.status is REPORTED
    assert decision.state.status is not CONFIRMED


def test_report_on_cash_is_rejected() -> None:
    with pytest.raises(InvalidPaymentTransitionError):
        apply_report(PaymentState(CASH, UNPAID))


# --- confirm: manual confirmation by an authorised participant ---------------------------

CONFIRM_ALLOWED = {
    PaymentState(CASH, UNPAID): PaymentDecision(PaymentState(CASH, CONFIRMED), changed=True),
    PaymentState(KASPI, UNPAID): PaymentDecision(PaymentState(KASPI, CONFIRMED), changed=True),
    PaymentState(KASPI, REPORTED): PaymentDecision(PaymentState(KASPI, CONFIRMED), changed=True),
    PaymentState(CASH, CONFIRMED): PaymentDecision(PaymentState(CASH, CONFIRMED), changed=False),
    PaymentState(KASPI, CONFIRMED): PaymentDecision(PaymentState(KASPI, CONFIRMED), changed=False),
}


@pytest.mark.parametrize("state", ALL_STATES, ids=state_id)
def test_confirm_matrix(state: PaymentState) -> None:
    expected = CONFIRM_ALLOWED.get(state)
    if expected is None:
        with pytest.raises(InvalidPaymentTransitionError) as caught:
            apply_confirm(state)
        assert caught.value.details["action"] == "confirm"
    else:
        assert apply_confirm(state) == expected


@pytest.mark.parametrize("method", list(PaymentMethod))
def test_repeated_confirm_is_already_confirmed_not_a_new_payment(method: PaymentMethod) -> None:
    first = apply_confirm(PaymentState(method, UNPAID))
    second = apply_confirm(first.state)

    assert first.changed is True
    assert second == PaymentDecision(PaymentState(method, CONFIRMED), changed=False)


# --- method change: the passenger picks cash or the Kaspi link ---------------------------


@pytest.mark.parametrize("kaspi_enabled", [True, False])
@pytest.mark.parametrize("state", ALL_STATES, ids=state_id)
def test_choosing_the_current_method_is_a_no_op(state: PaymentState, kaspi_enabled: bool) -> None:
    decision = apply_method_change(state, state.method, kaspi_enabled=kaspi_enabled)

    assert decision == PaymentDecision(state, changed=False)


def test_unpaid_cash_switches_to_kaspi_when_link_is_configured() -> None:
    decision = apply_method_change(PaymentState(CASH, UNPAID), KASPI, kaspi_enabled=True)

    assert decision == PaymentDecision(PaymentState(KASPI, UNPAID), changed=True)


def test_switch_to_kaspi_without_configured_link_is_unavailable() -> None:
    with pytest.raises(KaspiUnavailableError) as caught:
        apply_method_change(PaymentState(CASH, UNPAID), KASPI, kaspi_enabled=False)

    assert caught.value.status_code == 503
    assert caught.value.code == "kaspi_unavailable"


@pytest.mark.parametrize("status", [UNPAID, REPORTED])
@pytest.mark.parametrize("kaspi_enabled", [True, False])
def test_kaspi_switches_back_to_unpaid_cash(status: PaymentStatus, kaspi_enabled: bool) -> None:
    decision = apply_method_change(PaymentState(KASPI, status), CASH, kaspi_enabled=kaspi_enabled)

    assert decision == PaymentDecision(PaymentState(CASH, UNPAID), changed=True)


@pytest.mark.parametrize("kaspi_enabled", [True, False])
@pytest.mark.parametrize(
    ("state", "new_method"),
    [(PaymentState(CASH, CONFIRMED), KASPI), (PaymentState(KASPI, CONFIRMED), CASH)],
    ids=state_id,
)
def test_method_change_after_confirmation_is_rejected(
    state: PaymentState, new_method: PaymentMethod, kaspi_enabled: bool
) -> None:
    with pytest.raises(InvalidPaymentTransitionError) as caught:
        apply_method_change(state, new_method, kaspi_enabled=kaspi_enabled)

    assert caught.value.details == {
        "action": "change_method",
        "method": state.method.value,
        "status": "confirmed",
    }
