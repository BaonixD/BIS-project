"""A ride copies its quote's route and its tariff's price; ``tariff_version`` names the rates."""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import TextClause

from taxi_service.database.base import Base, UtcDateTime
from taxi_service.modules.rides.states import (
    ACTIVE_RIDE_STATUSES,
    OfferStatus,
    RideCommand,
    RideStatus,
)
from taxi_service.modules.rides.tariffs import TARIFFS, Tariff, tariff_check

if TYPE_CHECKING:
    from taxi_service.modules.payments.models import Payment

PROVIDER_MAX_LENGTH: Final = 32
TARIFF_VERSION_MAX_LENGTH: Final = 16
STATUS_MAX_LENGTH: Final = 16
OPERATION_MAX_LENGTH: Final = 32
IDEMPOTENCY_KEY_MAX_LENGTH: Final = 128
SHA256_HEX_LENGTH: Final = 64
REASON_MAX_LENGTH: Final = 200

ACTIVE_PASSENGER_RIDE_INDEX: Final = "uq_rides_active_passenger_id"
ACTIVE_DRIVER_RIDE_INDEX: Final = "uq_rides_active_driver_id"
PASSENGER_HISTORY_INDEX: Final = "ix_rides_passenger_id_created_at"
DRIVER_HISTORY_INDEX: Final = "ix_rides_driver_id_created_at"
SEARCHING_DEADLINE_INDEX: Final = "ix_rides_searching_search_deadline"
PENDING_OFFER_RIDE_INDEX: Final = "uq_ride_offers_pending_ride_id"
PENDING_OFFER_DRIVER_INDEX: Final = "uq_ride_offers_pending_driver_id"
PENDING_OFFER_EXPIRY_INDEX: Final = "ix_ride_offers_pending_expires_at"
SEARCH_OFFER_CONSTRAINT: Final = "uq_ride_offers_ride_id_driver_id_search_started_at"
RIDE_EVENTS_INDEX: Final = "ix_ride_events_ride_id_created_at"

# Statuses with an accepted driver; ``cancelled`` may keep the driver it had.
ASSIGNED_RIDE_STATUSES: Final = frozenset(
    {RideStatus.ASSIGNED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS, RideStatus.COMPLETED}
)
UNASSIGNED_RIDE_STATUSES: Final = frozenset({RideStatus.SEARCHING, RideStatus.NO_DRIVER})
ACCEPTED_ACTIVE_RIDE_STATUSES: Final = ACTIVE_RIDE_STATUSES - {RideStatus.SEARCHING}


def _sql_list(statuses: frozenset[RideStatus]) -> str:
    return ", ".join(f"'{status.value}'" for status in sorted(statuses))


def _status_in(statuses: frozenset[RideStatus]) -> TextClause:
    return text(f"status IN ({_sql_list(statuses)})")


SEARCHING: Final = text(f"status = '{RideStatus.SEARCHING.value}'")
PENDING_OFFER: Final = text(f"status = '{OfferStatus.PENDING.value}'")


def _values_in(column: str, enum: type[RideStatus | RideCommand]) -> str:
    return f"{column} IN ({', '.join(f"'{member.value}'" for member in sorted(enum))})"


def _string_enum[EnumT: (RideStatus, OfferStatus, RideCommand, Tariff)](enum: type[EnumT]) -> Enum:
    """Stored as its value in a VARCHAR; the CHECK constraint is declared by the table."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        length=STATUS_MAX_LENGTH,
        values_callable=lambda members: [member.value for member in members],
    )


def _route_checks() -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(
            "pickup_longitude BETWEEN -180 AND 180 AND dropoff_longitude BETWEEN -180 AND 180",
            name="longitude_range",
        ),
        CheckConstraint(
            "pickup_latitude BETWEEN -90 AND 90 AND dropoff_latitude BETWEEN -90 AND 90",
            name="latitude_range",
        ),
        CheckConstraint("distance_m >= 0 AND duration_s >= 0", name="route_metrics"),
        CheckConstraint("currency = 'KZT'", name="currency_kzt"),
    )


# A quote prices every tariff (ADR 0012); the ride keeps the price of the chosen one.
QUOTE_AMOUNT_COLUMNS: Final = {tariff: f"{tariff.value}_amount_kzt" for tariff in TARIFFS}


class RouteSnapshot:
    """Columns shared by a quote and its ride: points, road route and the tariff rates."""

    pickup_longitude: Mapped[float] = mapped_column(Float())
    pickup_latitude: Mapped[float] = mapped_column(Float())
    dropoff_longitude: Mapped[float] = mapped_column(Float())
    dropoff_latitude: Mapped[float] = mapped_column(Float())
    distance_m: Mapped[int] = mapped_column(Integer())
    duration_s: Mapped[int] = mapped_column(Integer())
    route_geometry: Mapped[dict[str, Any]] = mapped_column(JSON())
    provider: Mapped[str] = mapped_column(String(PROVIDER_MAX_LENGTH))
    currency: Mapped[str] = mapped_column(String(3))
    tariff_version: Mapped[str] = mapped_column(String(TARIFF_VERSION_MAX_LENGTH))


ROUTE_SNAPSHOT_COLUMNS: Final = tuple(RouteSnapshot.__annotations__)


class RideQuote(RouteSnapshot, Base):
    """Used by at most one ride (``rides.quote_id`` is unique)."""

    __tablename__ = "ride_quotes"
    __table_args__ = (
        *_route_checks(),
        CheckConstraint(
            " AND ".join(f"{column} > 0" for column in QUOTE_AMOUNT_COLUMNS.values()),
            name="amount_positive",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    economy_amount_kzt: Mapped[int] = mapped_column(Integer())
    comfort_amount_kzt: Mapped[int] = mapped_column(Integer())
    comfort_plus_amount_kzt: Mapped[int] = mapped_column(Integer())
    business_amount_kzt: Mapped[int] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())

    def amount_for(self, tariff: Tariff) -> int:
        amount: int = getattr(self, QUOTE_AMOUNT_COLUMNS[tariff])
        return amount

    def amounts(self) -> dict[Tariff, int]:
        """Cheapest tariff first."""
        return {tariff: self.amount_for(tariff) for tariff in TARIFFS}


class Ride(RouteSnapshot, Base):
    """Partial unique indexes: one active ride per passenger, one accepted per driver."""

    __tablename__ = "rides"
    __table_args__ = (
        *_route_checks(),
        CheckConstraint("amount_kzt > 0", name="amount_positive"),
        CheckConstraint(tariff_check("tariff"), name="tariff"),
        CheckConstraint(f"status IN ({_sql_list(frozenset(RideStatus))})", name="status"),
        CheckConstraint(
            f"(status IN ({_sql_list(UNASSIGNED_RIDE_STATUSES)}) AND driver_id IS NULL)"
            f" OR (status IN ({_sql_list(ASSIGNED_RIDE_STATUSES)}) AND driver_id IS NOT NULL)"
            f" OR status = '{RideStatus.CANCELLED.value}'",
            name="driver_matches_status",
        ),
        Index(
            ACTIVE_PASSENGER_RIDE_INDEX,
            "passenger_id",
            unique=True,
            sqlite_where=_status_in(ACTIVE_RIDE_STATUSES),
            postgresql_where=_status_in(ACTIVE_RIDE_STATUSES),
        ),
        Index(
            ACTIVE_DRIVER_RIDE_INDEX,
            "driver_id",
            unique=True,
            sqlite_where=_status_in(ACCEPTED_ACTIVE_RIDE_STATUSES),
            postgresql_where=_status_in(ACCEPTED_ACTIVE_RIDE_STATUSES),
        ),
        CheckConstraint("search_deadline > search_started_at", name="search_deadline_after_start"),
        # History of a passenger or a driver: ORDER BY created_at DESC, id DESC (T09).
        Index(PASSENGER_HISTORY_INDEX, "passenger_id", "created_at", "id"),
        Index(DRIVER_HISTORY_INDEX, "driver_id", "created_at", "id"),
        # The dispatch loop looks for searching rides only.
        Index(
            SEARCHING_DEADLINE_INDEX,
            "search_deadline",
            sqlite_where=SEARCHING,
            postgresql_where=SEARCHING,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("driver_profiles.user_id"))
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ride_quotes.id"), unique=True)
    tariff: Mapped[Tariff] = mapped_column(
        _string_enum(Tariff), server_default=Tariff.ECONOMY.value
    )
    amount_kzt: Mapped[int] = mapped_column(Integer())
    status: Mapped[RideStatus] = mapped_column(_string_enum(RideStatus))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
    search_started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    search_deadline: Mapped[datetime] = mapped_column(UtcDateTime())
    # Stage times of the current assignment and the end of the ride (ADR 0007).
    assigned_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    arrived_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cancel_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    # Opened with the order (ADR 0010); loaded with the ride for its responses.
    payment: Mapped["Payment | None"] = relationship(lazy="selectin")

    @classmethod
    def from_quote(
        cls, quote: RideQuote, tariff: Tariff, now: datetime, *, search_budget: timedelta
    ) -> "Ride":
        snapshot = {name: getattr(quote, name) for name in ROUTE_SNAPSHOT_COLUMNS}
        return cls(
            id=uuid.uuid4(),
            passenger_id=quote.passenger_id,
            driver_id=None,
            quote_id=quote.id,
            tariff=tariff,
            amount_kzt=quote.amount_for(tariff),
            status=RideStatus.SEARCHING,
            **snapshot,
            created_at=now,
            updated_at=now,
            search_started_at=now,
            search_deadline=now + search_budget,
        )


class RideOffer(Base):
    """Unique by status, not time: an overdue pending offer blocks until marked expired."""

    __tablename__ = "ride_offers"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(f"'{status.value}'" for status in sorted(OfferStatus))})",
            name="status",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint(
            f"(status = '{OfferStatus.PENDING.value}' AND responded_at IS NULL)"
            f" OR (status <> '{OfferStatus.PENDING.value}' AND responded_at IS NOT NULL)",
            name="responded_matches_status",
        ),
        UniqueConstraint("ride_id", "driver_id", "search_started_at"),
        Index(
            PENDING_OFFER_RIDE_INDEX,
            "ride_id",
            unique=True,
            sqlite_where=PENDING_OFFER,
            postgresql_where=PENDING_OFFER,
        ),
        Index(
            PENDING_OFFER_DRIVER_INDEX,
            "driver_id",
            unique=True,
            sqlite_where=PENDING_OFFER,
            postgresql_where=PENDING_OFFER,
        ),
        Index(
            PENDING_OFFER_EXPIRY_INDEX,
            "expires_at",
            sqlite_where=PENDING_OFFER,
            postgresql_where=PENDING_OFFER,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"))
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("driver_profiles.user_id"))
    status: Mapped[OfferStatus] = mapped_column(_string_enum(OfferStatus))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    responded_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    search_started_at: Mapped[datetime] = mapped_column(UtcDateTime())


class RideEvent(Base):
    """``actor_id`` is ``NULL`` for the dispatch loop."""

    __tablename__ = "ride_events"
    __table_args__ = (
        CheckConstraint(_values_in("from_status", RideStatus), name="from_status"),
        CheckConstraint(_values_in("to_status", RideStatus), name="to_status"),
        CheckConstraint(_values_in("command", RideCommand), name="command"),
        CheckConstraint(
            f"reason IS NULL OR length(reason) BETWEEN 1 AND {REASON_MAX_LENGTH}",
            name="reason_length",
        ),
        Index(RIDE_EVENTS_INDEX, "ride_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"))
    from_status: Mapped[RideStatus] = mapped_column(_string_enum(RideStatus))
    to_status: Mapped[RideStatus] = mapped_column(_string_enum(RideStatus))
    command: Mapped[RideCommand] = mapped_column(_string_enum(RideCommand))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class IdempotencyRecord(Base):
    """Kept at least 24 hours; cleanup is a later task (ADR 0005)."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "key"),
        CheckConstraint(
            f"length(key) BETWEEN 1 AND {IDEMPOTENCY_KEY_MAX_LENGTH}", name="key_length"
        ),
        CheckConstraint(
            f"length(request_fingerprint) = {SHA256_HEX_LENGTH}", name="fingerprint_length"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(OPERATION_MAX_LENGTH))
    key: Mapped[str] = mapped_column(String(IDEMPOTENCY_KEY_MAX_LENGTH))
    request_fingerprint: Mapped[str] = mapped_column(String(SHA256_HEX_LENGTH))
    resource_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
