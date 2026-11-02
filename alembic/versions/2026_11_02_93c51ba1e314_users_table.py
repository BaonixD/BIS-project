"""users: accounts with a local password and a role

Revision ID: 93c51ba1e314
Revises: dea9719c6061
Create Date: 2026-11-02 20:21:57.535548+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "93c51ba1e314"
down_revision: str | Sequence[str] | None = "dea9719c6061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("username_normalized", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username_normalized", name=op.f("uq_users_username_normalized")),
        sa.CheckConstraint(
            "username_normalized = lower(username)", name=op.f("ck_users_username_normalized")
        ),
        sa.CheckConstraint("role IN ('passenger', 'driver', 'admin')", name=op.f("ck_users_role")),
    )


def downgrade() -> None:
    op.drop_table("users")
