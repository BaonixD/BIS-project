"""Quotes, rides and idempotency records (MVP_SPEC §5, §6).

A ride copies the route and the fare of its quote: later tariff changes never
reach a stored quote or ride, ``tariff_version`` says which tariff priced it.
"""

import uuid
from datetime import datetime
from typing import Any, Final

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
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import TextClause

from taxi_service.database.base import Base, UtcDateTime
from taxi_service.modules.rides.states import ACTIVE_RIDE_STATUSES, RideStatus

PROVIDER_MAX_LENGTH: Final = 32
TARIFF_VERSION_MAX_LENGTH: Final = 16
STATUS_MAX_LENGTH: Final = 16
OPERATION_MAX_LENGTH: Final = 32
IDEMPOTENCY_KEY_MAX_LENGTH: Final = 128
SHA256_HEX_LENGTH: Final = 64

ACTIVE_PASSENGER_RIDE_INDEX: Final = "uq_rides_active_passenger_id"
ACTIVE_DRIVER_RIDE_INDEX: Final = "uq_rides_active_driver_id"

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
        CheckConstraint("amount_kzt > 0", name="amount_positive"),
        CheckConstraint("currency = 'KZT'", name="currency_kzt"),
    )


class RouteSnapshot:
    """Columns shared by a quote and its ride: points, road route and fixed fare."""

    pickup_longitude: Mapped[float] = mapped_column(Float())
    pickup_latitude: Mapped[float] = mapped_column(Float())
    dropoff_longitude: Mapped[float] = mapped_column(Float())
    dropoff_latitude: Mapped[float] = mapped_column(Float())
    distance_m: Mapped[int] = mapped_column(Integer())
    duration_s: Mapped[int] = mapped_column(Integer())
    route_geometry: Mapped[dict[str, Any]] = mapped_column(JSON())
    provider: Mapped[str] = mapped_column(String(PROVIDER_MAX_LENGTH))
    amount_kzt: Mapped[int] = mapped_column(Integer())
    currency: Mapped[str] = mapped_column(String(3))
    tariff_version: Mapped[str] = mapped_column(String(TARIFF_VERSION_MAX_LENGTH))


ROUTE_SNAPSHOT_COLUMNS: Final = tuple(RouteSnapshot.__annotations__)


class RideQuote(RouteSnapshot, Base):
    """Server-side price offer for a route of one passenger; valid until ``expires_at``.

    A quote is used by at most one ride (``rides.quote_id`` is unique).
    """

    __tablename__ = "ride_quotes"
    __table_args__ = (
        *_route_checks(),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class Ride(RouteSnapshot, Base):
    """A passenger's order with the route and fare copied from its quote.

    The database enforces the limits of MVP_SPEC §6: one active ride per
    passenger, one accepted active ride per driver (partial unique indexes),
    and a driver that matches the status — none while ``searching`` or
    ``no_driver``, one from ``assigned`` on; a ``cancelled`` ride keeps
    whatever it had, because it is cancelled before or after assignment.
    """

    __tablename__ = "rides"
    __table_args__ = (
        *_route_checks(),
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
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("driver_profiles.user_id"))
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ride_quotes.id"), unique=True)
    status: Mapped[RideStatus] = mapped_column(
        Enum(
            RideStatus,
            native_enum=False,
            create_constraint=False,
            length=STATUS_MAX_LENGTH,
            values_callable=lambda statuses: [status.value for status in statuses],
        )
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())

    @classmethod
    def from_quote(cls, quote: RideQuote, now: datetime) -> "Ride":
        """New ``searching`` ride without a driver; route and fare copied from the quote."""
        snapshot = {name: getattr(quote, name) for name in ROUTE_SNAPSHOT_COLUMNS}
        return cls(
            id=uuid.uuid4(),
            passenger_id=quote.passenger_id,
            driver_id=None,
            quote_id=quote.id,
            status=RideStatus.SEARCHING,
            **snapshot,
            created_at=now,
            updated_at=now,
        )


class IdempotencyRecord(Base):
    """Result of a successful idempotent command, scoped by user and operation.

    ``request_fingerprint`` is the SHA-256 of the canonical request body;
    ``resource_id`` is what the first request created (a ride id for
    ``create_ride``). Kept at least 24 hours; cleanup is a later task, until
    then records stay (ADR 0005).
    """

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
