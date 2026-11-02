"""Pure payment rules: statuses, methods and allowed transitions (MVP_SPEC section 7)."""

from collections.abc import Mapping
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


_CASH = PaymentMethod.CASH
_KASPI = PaymentMethod.KASPI_LINK

# (action, method, from status) -> to status. Repeating an action on its target is a no-op.
_TRANSITIONS: Final[Mapping[tuple[PaymentAction, PaymentMethod, PaymentStatus], PaymentStatus]] = {
    (PaymentAction.REPORT, _KASPI, PaymentStatus.UNPAID): PaymentStatus.REPORTED,
    (PaymentAction.CONFIRM, _CASH, PaymentStatus.UNPAID): PaymentStatus.CONFIRMED,
    (PaymentAction.CONFIRM, _KASPI, PaymentStatus.UNPAID): PaymentStatus.CONFIRMED,
    (PaymentAction.CONFIRM, _KASPI, PaymentStatus.REPORTED): PaymentStatus.CONFIRMED,
}
_TARGETS: Final = frozenset(
    (action, method, target) for (action, method, _), target in _TRANSITIONS.items()
)


def apply_report(state: PaymentState) -> PaymentDecision:
    """Passenger statement for a Kaspi payment; it never confirms the payment."""
    return _apply(PaymentAction.REPORT, state)


def apply_confirm(state: PaymentState) -> PaymentDecision:
    """Manual confirmation; repeating it on a confirmed payment changes nothing."""
    return _apply(PaymentAction.CONFIRM, state)


def _apply(action: PaymentAction, state: PaymentState) -> PaymentDecision:
    target = _TRANSITIONS.get((action, state.method, state.status))
    if target is not None:
        return PaymentDecision(PaymentState(state.method, target), changed=True)
    if (action, state.method, state.status) in _TARGETS:
        return PaymentDecision(state, changed=False)
    raise _invalid(action, state)


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
