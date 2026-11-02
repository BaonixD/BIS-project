"""ride_quotes, rides and idempotency_records: priced quotes, rides and request replay

Revision ID: 640cf8e50671
Revises: e87ec15b6147
Create Date: 2026-11-02 21:25:44.749085+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "640cf8e50671"
down_revision: str | Sequence[str] | None = "e87ec15b6147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE = "status IN ('arrived', 'assigned', 'in_progress', 'searching')"
ACCEPTED_ACTIVE = "status IN ('arrived', 'assigned', 'in_progress')"


def route_snapshot_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("pickup_longitude", sa.Float(), nullable=False),
        sa.Column("pickup_latitude", sa.Float(), nullable=False),
        sa.Column("dropoff_longitude", sa.Float(), nullable=False),
        sa.Column("dropoff_latitude", sa.Float(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("route_geometry", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("amount_kzt", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("tariff_version", sa.String(length=16), nullable=False),
    ]


def route_snapshot_checks(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "pickup_longitude BETWEEN -180 AND 180 AND dropoff_longitude BETWEEN -180 AND 180",
            name=op.f(f"ck_{table}_longitude_range"),
        ),
        sa.CheckConstraint(
            "pickup_latitude BETWEEN -90 AND 90 AND dropoff_latitude BETWEEN -90 AND 90",
            name=op.f(f"ck_{table}_latitude_range"),
        ),
        sa.CheckConstraint(
            "distance_m >= 0 AND duration_s >= 0", name=op.f(f"ck_{table}_route_metrics")
        ),
        sa.CheckConstraint("amount_kzt > 0", name=op.f(f"ck_{table}_amount_positive")),
        sa.CheckConstraint("currency = 'KZT'", name=op.f(f"ck_{table}_currency_kzt")),
    ]


def upgrade() -> None:
    op.create_table(
        "ride_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("passenger_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *route_snapshot_columns(),
        *route_snapshot_checks("ride_quotes"),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_ride_quotes_expires_after_created")
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"], ["users.id"], name=op.f("fk_ride_quotes_passenger_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_quotes")),
    )
    op.create_index("ix_ride_quotes_passenger_id", "ride_quotes", ["passenger_id"])

    op.create_table(
        "rides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("passenger_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=True),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *route_snapshot_columns(),
        *route_snapshot_checks("rides"),
        sa.CheckConstraint(
            "status IN ('arrived', 'assigned', 'cancelled', 'completed', 'in_progress',"
            " 'no_driver', 'searching')",
            name=op.f("ck_rides_status"),
        ),
        # No driver while searching/no_driver, a driver from assigned on;
        # a cancelled ride keeps what it had (cancelled before or after assignment).
        sa.CheckConstraint(
            "(status IN ('no_driver', 'searching') AND driver_id IS NULL)"
            " OR (status IN ('arrived', 'assigned', 'completed', 'in_progress')"
            " AND driver_id IS NOT NULL)"
            " OR status = 'cancelled'",
            name=op.f("ck_rides_driver_matches_status"),
        ),
        sa.ForeignKeyConstraint(
            ["passenger_id"], ["users.id"], name=op.f("fk_rides_passenger_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["driver_profiles.user_id"],
            name=op.f("fk_rides_driver_id_driver_profiles"),
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["ride_quotes.id"], name=op.f("fk_rides_quote_id_ride_quotes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rides")),
        sa.UniqueConstraint("quote_id", name=op.f("uq_rides_quote_id")),
    )
    # One active ride per passenger, one accepted active ride per driver (MVP_SPEC §6).
    op.create_index(
        "uq_rides_active_passenger_id",
        "rides",
        ["passenger_id"],
        unique=True,
        sqlite_where=sa.text(ACTIVE),
        postgresql_where=sa.text(ACTIVE),
    )
    op.create_index(
        "uq_rides_active_driver_id",
        "rides",
        ["driver_id"],
        unique=True,
        sqlite_where=sa.text(ACCEPTED_ACTIVE),
        postgresql_where=sa.text(ACCEPTED_ACTIVE),
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(key) BETWEEN 1 AND 128", name=op.f("ck_idempotency_records_key_length")
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name=op.f("ck_idempotency_records_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_idempotency_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint(
            "user_id", "operation", "key", name=op.f("uq_idempotency_records_user_id_operation_key")
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("uq_rides_active_driver_id", table_name="rides")
    op.drop_index("uq_rides_active_passenger_id", table_name="rides")
    op.drop_table("rides")
    op.drop_index("ix_ride_quotes_passenger_id", table_name="ride_quotes")
    op.drop_table("ride_quotes")
