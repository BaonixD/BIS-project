"""Preserve routing traffic metadata with the agreed quote and ride snapshot."""

import sqlalchemy as sa
from alembic import op

revision = "3c6a9d41b072"
down_revision = "78463ec05d38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("ride_quotes", "rides"):
        op.add_column(
            table,
            sa.Column(
                "routing_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
            ),
        )


def downgrade() -> None:
    for table in ("rides", "ride_quotes"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("routing_metadata")
