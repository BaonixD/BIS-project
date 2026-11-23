"""Passenger bonuses: a wallet with a non-negative balance and an append-only history."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Final

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime

KIND_MAX_LENGTH: Final = 16
ONCE_PER_RIDE: Final = "kind IN ('earn', 'return')"


class BonusKind(StrEnum):
    EARN = "earn"
    SPEND = "spend"
    RETURN = "return"


class BonusWallet(Base):
    __tablename__ = "bonus_wallets"
    __table_args__ = (CheckConstraint("balance_kzt >= 0", name="balance"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_kzt: Mapped[int] = mapped_column(Integer())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())


class BonusEntry(Base):
    """A ride earns once and returns its spent bonuses once; it may spend more than once."""

    __tablename__ = "bonus_entries"
    __table_args__ = (
        CheckConstraint("amount_kzt > 0", name="amount"),
        CheckConstraint("kind IN ('earn','spend','return')", name="kind"),
        Index("ix_bonus_entries_user_created", "user_id", "created_at"),
        Index(
            "uq_bonus_entries_ride_kind_once",
            "ride_id",
            "kind",
            unique=True,
            sqlite_where=text(ONCE_PER_RIDE),
            postgresql_where=text(ONCE_PER_RIDE),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"))
    kind: Mapped[BonusKind] = mapped_column(
        Enum(
            BonusKind,
            native_enum=False,
            create_constraint=False,
            length=KIND_MAX_LENGTH,
            values_callable=lambda members: [member.value for member in members],
        )
    )
    amount_kzt: Mapped[int] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
