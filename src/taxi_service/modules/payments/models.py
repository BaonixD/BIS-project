"""CHECK constraints keep a payment consistent on their own (ADR 0004)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Final

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime

VALUE_MAX_LENGTH: Final = 16


class PaymentMethod(StrEnum):
    CASH = "cash"
    KASPI_LINK = "kaspi_link"


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"


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


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kzt > 0", name="amount_positive"),
        CheckConstraint("currency = 'KZT'", name="currency_kzt"),
        CheckConstraint(_values_in("method", PaymentMethod), name="method"),
        CheckConstraint(_values_in("status", PaymentStatus), name="status"),
        CheckConstraint(
            f"(status = '{PaymentStatus.UNPAID.value}' AND paid_at IS NULL)"
            f" OR (status = '{PaymentStatus.PAID.value}' AND paid_at IS NOT NULL)",
            name="paid_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"), unique=True)
    amount_kzt: Mapped[int] = mapped_column(Integer())
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[PaymentMethod] = mapped_column(_string_enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(_string_enum(PaymentStatus))
    paid_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
