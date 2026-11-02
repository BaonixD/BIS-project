"""ride_offers: 30-second offers of a ride to one driver

Revision ID: 5d2e4cb65b5e
Revises: 8deb4121d135
Create Date: 2026-11-03 10:05:00.000000+00:00

One pending offer per ride and per driver; the partial indexes depend on the
status only, never on the current time (MVP_SPEC §6, ADR 0006).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d2e4cb65b5e"
down_revision: str | Sequence[str] | None = "8deb4121d135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PENDING = "status = 'pending'"


def upgrade() -> None:
    op.create_table(
        "ride_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('accepted', 'expired', 'pending', 'rejected', 'revoked')",
            name=op.f("ck_ride_offers_status"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_ride_offers_expires_after_created")
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL)"
            " OR (status <> 'pending' AND responded_at IS NOT NULL)",
            name=op.f("ck_ride_offers_responded_matches_status"),
        ),
        sa.ForeignKeyConstraint(
            ["ride_id"], ["rides.id"], name=op.f("fk_ride_offers_ride_id_rides")
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["driver_profiles.user_id"],
            name=op.f("fk_ride_offers_driver_id_driver_profiles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_offers")),
        sa.UniqueConstraint("ride_id", "driver_id", name=op.f("uq_ride_offers_ride_id_driver_id")),
    )
    op.create_index(
        "uq_ride_offers_pending_ride_id",
        "ride_offers",
        ["ride_id"],
        unique=True,
        sqlite_where=sa.text(PENDING),
        postgresql_where=sa.text(PENDING),
    )
    op.create_index(
        "uq_ride_offers_pending_driver_id",
        "ride_offers",
        ["driver_id"],
        unique=True,
        sqlite_where=sa.text(PENDING),
        postgresql_where=sa.text(PENDING),
    )
    op.create_index(
        "ix_ride_offers_pending_expires_at",
        "ride_offers",
        ["expires_at"],
        sqlite_where=sa.text(PENDING),
        postgresql_where=sa.text(PENDING),
    )


def downgrade() -> None:
    op.drop_index("ix_ride_offers_pending_expires_at", table_name="ride_offers")
    op.drop_index("uq_ride_offers_pending_driver_id", table_name="ride_offers")
    op.drop_index("uq_ride_offers_pending_ride_id", table_name="ride_offers")
    op.drop_table("ride_offers")
