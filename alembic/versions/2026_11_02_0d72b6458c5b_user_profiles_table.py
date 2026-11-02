"""user_profiles: optional display name and phone of any user

Revision ID: 0d72b6458c5b
Revises: 64eda4a304e2
Create Date: 2026-11-02 20:57:49.701285+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0d72b6458c5b"
down_revision: str | Sequence[str] | None = "64eda4a304e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "phone IS NULL OR (substr(phone, 1, 1) = '+' AND length(phone) BETWEEN 11 AND 16)",
            name=op.f("ck_user_profiles_phone_format"),
        ),
        sa.CheckConstraint(
            "display_name IS NULL OR length(display_name) BETWEEN 1 AND 64",
            name=op.f("ck_user_profiles_display_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_profiles")),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
