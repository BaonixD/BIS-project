"""Payment record of a completed ride and its audit history (MVP_SPEC §7, ADR 0004).

One payment per ride, opened unpaid in cash by the completion of the ride
with the amount of the ride's server snapshot. Its CHECK constraints keep the
state consistent on their own: only a Kaspi payment is ever ``reported``, a
``confirmed`` one says who confirmed it and when, and a confirmed Kaspi
payment carries the reconciliation note. Verification is always manual.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Final

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime
from taxi_service.modules.payments.permissions import MAX_CONFIRMATION_REFERENCE_LENGTH
from taxi_service.modules.payments.rules import (
    PaymentAction,
    PaymentMethod,
    PaymentStatus,
    Verification,
)

VALUE_MAX_LENGTH: Final = 16
PAYMENT_EVENTS_INDEX: Final = "ix_payment_events_payment_id_created_at"


class PaymentEventAction(StrEnum):
    """What an audit row records: the opening by the system, or a payment action."""

    OPEN = "open"
    REPORT = PaymentAction.REPORT.value
    CONFIRM = PaymentAction.CONFIRM.value
    CHANGE_METHOD = PaymentAction.CHANGE_METHOD.value


def _values_in(column: str, enum: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(f"'{member.value}'" for member in sorted(enum))})"


def _string_enum(enum: type[StrEnum]) -> Enum:
    """Stored as its value in a VARCHAR; the CHECK constraint is declared by the table."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        length=VALUE_MAX_LENGTH,
        values_callable=lambda members: [member.value for member in members],
    )


def _reference_length(column: str) -> str:
    return f"{column} IS NULL OR length({column}) BETWEEN 1 AND {MAX_CONFIRMATION_REFERENCE_LENGTH}"


_CONFIRMED: Final = f"status = '{PaymentStatus.CONFIRMED.value}'"
_KASPI: Final = f"method = '{PaymentMethod.KASPI_LINK.value}'"


class Payment(Base):
    """The payment of one ride: amount copied from the ride, method, status, who confirmed.

    ``reported_at`` is the passenger's statement for Kaspi (cleared when the
    method changes back to cash); ``confirmed_at``/``confirmed_by`` and the
    optional ``confirmation_reference`` record the manual confirmation.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kzt > 0", name="amount_positive"),
        CheckConstraint("currency = 'KZT'", name="currency_kzt"),
        CheckConstraint(_values_in("method", PaymentMethod), name="method"),
        CheckConstraint(_values_in("status", PaymentStatus), name="status"),
        CheckConstraint(_values_in("verification", Verification), name="verification"),
        CheckConstraint(
            f"({_CONFIRMED} AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)"
            f" OR (NOT ({_CONFIRMED}) AND confirmed_at IS NULL AND confirmed_by IS NULL"
            " AND confirmation_reference IS NULL)",
            name="confirmed_matches_status",
        ),
        CheckConstraint(
            f"(status = '{PaymentStatus.UNPAID.value}' AND reported_at IS NULL)"
            f" OR (status = '{PaymentStatus.REPORTED.value}' AND reported_at IS NOT NULL)"
            f" OR {_CONFIRMED}",
            name="reported_matches_status",
        ),
        CheckConstraint(f"reported_at IS NULL OR {_KASPI}", name="report_only_kaspi"),
        CheckConstraint(
            f"NOT ({_CONFIRMED} AND {_KASPI}) OR confirmation_reference IS NOT NULL",
            name="kaspi_confirmation_reference",
        ),
        CheckConstraint(
            _reference_length("confirmation_reference"), name="confirmation_reference_length"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"), unique=True)
    amount_kzt: Mapped[int] = mapped_column(Integer())
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[PaymentMethod] = mapped_column(_string_enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(_string_enum(PaymentStatus))
    verification: Mapped[Verification] = mapped_column(_string_enum(Verification))
    reported_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmation_reference: Mapped[str | None] = mapped_column(
        String(MAX_CONFIRMATION_REFERENCE_LENGTH)
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())


class PaymentEvent(Base):
    """One audited change of a payment, written in the transaction of the change.

    ``open`` has no previous state and no actor (the completion of the ride);
    every other row names the user who acted. Only a confirmation carries the
    reconciliation note. An idempotent repeat writes no row.
    """

    __tablename__ = "payment_events"
    __table_args__ = (
        CheckConstraint(_values_in("action", PaymentEventAction), name="action"),
        CheckConstraint(
            f"from_status IS NULL OR {_values_in('from_status', PaymentStatus)}",
            name="from_status",
        ),
        CheckConstraint(_values_in("to_status", PaymentStatus), name="to_status"),
        CheckConstraint(
            f"from_method IS NULL OR {_values_in('from_method', PaymentMethod)}",
            name="from_method",
        ),
        CheckConstraint(_values_in("to_method", PaymentMethod), name="to_method"),
        CheckConstraint(
            f"(action = '{PaymentEventAction.OPEN.value}'"
            " AND from_status IS NULL AND from_method IS NULL)"
            f" OR (action <> '{PaymentEventAction.OPEN.value}'"
            " AND from_status IS NOT NULL AND from_method IS NOT NULL)",
            name="previous_state",
        ),
        CheckConstraint(
            f"reference IS NULL OR action = '{PaymentEventAction.CONFIRM.value}'",
            name="reference_only_confirm",
        ),
        CheckConstraint(_reference_length("reference"), name="reference_length"),
        Index(PAYMENT_EVENTS_INDEX, "payment_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"))
    action: Mapped[PaymentEventAction] = mapped_column(_string_enum(PaymentEventAction))
    from_status: Mapped[PaymentStatus | None] = mapped_column(_string_enum(PaymentStatus))
    to_status: Mapped[PaymentStatus] = mapped_column(_string_enum(PaymentStatus))
    from_method: Mapped[PaymentMethod | None] = mapped_column(_string_enum(PaymentMethod))
    to_method: Mapped[PaymentMethod] = mapped_column(_string_enum(PaymentMethod))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reference: Mapped[str | None] = mapped_column(String(MAX_CONFIRMATION_REFERENCE_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
