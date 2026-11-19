"""Allow uploads without parsing PDFs for a page count."""

import sqlalchemy as sa
from alembic import op

revision = "8a0ee43fd0b2"
down_revision = "3c6a9d41b072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("driver_documents") as batch:
        batch.drop_constraint(op.f("ck_driver_documents_page_count"), type_="check")
        batch.alter_column("page_count", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    raise NotImplementedError("Uploaded documents may have no page count.")
