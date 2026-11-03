"""ride_ratings and ride_rating_tags: one rating per side of a ride (ADR 0013)

Revision ID: d9f6c93e85a9
Revises: 4dc8bde81ded
Create Date: 2026-11-03 23:00:00.000000+00:00

Two new tables, no existing data changes. Tags are rows of their own table
(one per tag) so the database checks every value. Downgrade drops both tables
with the ratings in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f6c93e85a9"
down_revision: str | Sequence[str] | None = "4dc8bde81ded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TAGS = "'clean', 'clean_car', 'knows_route', 'on_time', 'polite', 'smooth_driving'"


def upgrade() -> None:
    op.create_table(
        "ride_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("rater_id", sa.Uuid(), nullable=False),
        sa.Column("rater_role", sa.String(length=16), nullable=False),
        sa.Column("ratee_id", sa.Uuid(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name=op.f("ck_ride_ratings_stars_range")),
        sa.CheckConstraint(
            "rater_role IN ('driver', 'passenger')", name=op.f("ck_ride_ratings_rater_role")
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(comment) BETWEEN 1 AND 500",
            name=op.f("ck_ride_ratings_comment_length"),
        ),
        sa.CheckConstraint("rater_id <> ratee_id", name=op.f("ck_ride_ratings_not_self")),
        sa.ForeignKeyConstraint(
            ["ride_id"], ["rides.id"], name=op.f("fk_ride_ratings_ride_id_rides")
        ),
        sa.ForeignKeyConstraint(
            ["rater_id"], ["users.id"], name=op.f("fk_ride_ratings_rater_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["ratee_id"], ["users.id"], name=op.f("fk_ride_ratings_ratee_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_ratings")),
        sa.UniqueConstraint(
            "ride_id", "rater_role", name=op.f("uq_ride_ratings_ride_id_rater_role")
        ),
    )
    op.create_index("ix_ride_ratings_ratee_id_stars", "ride_ratings", ["ratee_id", "stars"])
    op.create_table(
        "ride_rating_tags",
        sa.Column("rating_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=16), nullable=False),
        sa.CheckConstraint(f"tag IN ({TAGS})", name=op.f("ck_ride_rating_tags_tag")),
        sa.ForeignKeyConstraint(
            ["rating_id"],
            ["ride_ratings.id"],
            name=op.f("fk_ride_rating_tags_rating_id_ride_ratings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("rating_id", "tag", name=op.f("pk_ride_rating_tags")),
    )


def downgrade() -> None:
    op.drop_table("ride_rating_tags")
    op.drop_index("ix_ride_ratings_ratee_id_stars", table_name="ride_ratings")
    op.drop_table("ride_ratings")
