"""driver_profiles and vehicles: driver data, approval, location and one car per driver

Revision ID: e87ec15b6147
Revises: 0d72b6458c5b
Create Date: 2026-11-02 21:05:21.732608+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e87ec15b6147"
down_revision: str | Sequence[str] | None = "0d72b6458c5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "driver_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=16), nullable=True),
        sa.Column("license_number", sa.String(length=20), nullable=True),
        sa.Column("approval_status", sa.String(length=16), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(approval_status = 'approved' AND approved_at IS NOT NULL AND approved_by IS NOT NULL)"
            " OR (approval_status = 'pending' AND approved_at IS NULL AND approved_by IS NULL)",
            name=op.f("ck_driver_profiles_approval_recorded"),
        ),
        sa.CheckConstraint(
            "NOT is_online OR approval_status = 'approved'",
            name=op.f("ck_driver_profiles_online_requires_approval"),
        ),
        sa.CheckConstraint(
            "approval_status IN ('pending', 'approved')",
            name=op.f("ck_driver_profiles_approval_status"),
        ),
        sa.CheckConstraint(
            "(longitude IS NULL AND latitude IS NULL AND location_updated_at IS NULL)"
            " OR (longitude IS NOT NULL AND latitude IS NOT NULL"
            " AND location_updated_at IS NOT NULL)",
            name=op.f("ck_driver_profiles_location_complete"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_driver_profiles_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_driver_profiles_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_driver_profiles_approved_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_driver_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_driver_profiles")),
    )
    # Bounding-box prefilter of the nearest-driver search (ADR 0001).
    op.create_index(
        "ix_driver_profiles_longitude_latitude", "driver_profiles", ["longitude", "latitude"]
    )

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("make", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("plate_number", sa.String(length=10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "plate_number = upper(plate_number) AND length(plate_number) BETWEEN 4 AND 10",
            name=op.f("ck_vehicles_plate_number_normalized"),
        ),
        sa.CheckConstraint("year BETWEEN 1980 AND 2100", name=op.f("ck_vehicles_year_range")),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["driver_profiles.user_id"],
            name=op.f("fk_vehicles_driver_id_driver_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
        sa.UniqueConstraint("driver_id", name=op.f("uq_vehicles_driver_id")),
        sa.UniqueConstraint("plate_number", name=op.f("uq_vehicles_plate_number")),
    )


def downgrade() -> None:
    op.drop_table("vehicles")
    op.drop_index("ix_driver_profiles_longitude_latitude", table_name="driver_profiles")
    op.drop_table("driver_profiles")
