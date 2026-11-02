"""Pure payment rules: statuses, methods and allowed transitions (MVP_SPEC section 7)."""

from dataclasses import dataclass
from enum import StrEnum


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
    return PaymentDecision(state, changed=True)


def apply_confirm(state: PaymentState) -> PaymentDecision:
    return PaymentDecision(state, changed=True)


def apply_method_change(
    state: PaymentState, new_method: PaymentMethod, *, kaspi_enabled: bool
) -> PaymentDecision:
    return PaymentDecision(state, changed=True)
