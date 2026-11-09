"""Admin account access controls.

Revision ID: c6f8a4d219e0
Revises: d9f6c93e85a9
"""

import sqlalchemy as sa
from alembic import op

revision = "c6f8a4d219e0"
down_revision = "d9f6c93e85a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("block_reason", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("blocked_by", sa.Uuid(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("blocked_by")
        batch.drop_column("block_reason")
        batch.drop_column("blocked_at")
