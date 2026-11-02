"""Pure payment rules: statuses, methods and allowed transitions (MVP_SPEC section 7)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from taxi_service.modules.payments.exceptions import (
    InvalidPaymentTransitionError,
    KaspiUnavailableError,
)


class PaymentMethod(StrEnum):
    CASH = "cash"
    KASPI_LINK = "kaspi_link"


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    REPORTED = "reported"
    CONFIRMED = "confirmed"


class Verification(StrEnum):
    MANUAL = "manual"


class PaymentAction(StrEnum):
    REPORT = "report"
    CONFIRM = "confirm"
    CHANGE_METHOD = "change_method"


@dataclass(frozen=True, slots=True)
class PaymentState:
    method: PaymentMethod
    status: PaymentStatus


@dataclass(frozen=True, slots=True)
class PaymentDecision:
    """Result of a command; ``changed`` is false for an idempotent repeat."""

    state: PaymentState
    changed: bool


def initial_payment_state() -> PaymentState:
    return PaymentState(PaymentMethod.CASH, PaymentStatus.UNPAID)


def apply_report(state: PaymentState) -> PaymentDecision:
    """Passenger statement for a Kaspi payment; it never confirms the payment."""
    if state == PaymentState(PaymentMethod.KASPI_LINK, PaymentStatus.REPORTED):
        return PaymentDecision(state, changed=False)
    if state != PaymentState(PaymentMethod.KASPI_LINK, PaymentStatus.UNPAID):
        raise _invalid(PaymentAction.REPORT, state)
    return PaymentDecision(PaymentState(state.method, PaymentStatus.REPORTED), changed=True)


_CONFIRMABLE: Final = frozenset(
    {
        PaymentState(PaymentMethod.CASH, PaymentStatus.UNPAID),
        PaymentState(PaymentMethod.KASPI_LINK, PaymentStatus.UNPAID),
        PaymentState(PaymentMethod.KASPI_LINK, PaymentStatus.REPORTED),
    }
)


def apply_confirm(state: PaymentState) -> PaymentDecision:
    """Manual confirmation; repeating it on a confirmed payment changes nothing."""
    if state.status is PaymentStatus.CONFIRMED:
        return PaymentDecision(state, changed=False)
    if state not in _CONFIRMABLE:
        raise _invalid(PaymentAction.CONFIRM, state)
    return PaymentDecision(PaymentState(state.method, PaymentStatus.CONFIRMED), changed=True)


def apply_method_change(
    state: PaymentState, new_method: PaymentMethod, *, kaspi_enabled: bool
) -> PaymentDecision:
    """Switch before confirmation; a Kaspi statement does not carry over to cash."""
    if new_method is state.method:
        return PaymentDecision(state, changed=False)
    if state.status is PaymentStatus.CONFIRMED:
        raise _invalid(PaymentAction.CHANGE_METHOD, state)
    if new_method is PaymentMethod.KASPI_LINK and not kaspi_enabled:
        raise KaspiUnavailableError()
    return PaymentDecision(PaymentState(new_method, PaymentStatus.UNPAID), changed=True)


def _invalid(action: PaymentAction, state: PaymentState) -> InvalidPaymentTransitionError:
    return InvalidPaymentTransitionError(
        action=action.value, method=state.method.value, status=state.status.value
    )
