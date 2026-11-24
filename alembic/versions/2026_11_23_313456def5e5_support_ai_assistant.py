"""FAQ assistant in support: message authorship and a ticket's AI state."""

import sqlalchemy as sa
from alembic import op

revision = "313456def5e5"
down_revision = "8a0ee43fd0b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("support_tickets") as batch:
        batch.add_column(
            sa.Column("support_mode", sa.String(length=8), server_default="human", nullable=False)
        )
        batch.add_column(
            sa.Column("ai_state", sa.String(length=8), server_default="idle", nullable=False)
        )
        batch.add_column(sa.Column("ai_source_seq", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ai_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            op.f("ck_support_tickets_support_mode"), "support_mode IN ('ai','human')"
        )
        batch.create_check_constraint(
            op.f("ck_support_tickets_ai_state"), "ai_state IN ('idle','pending','running','failed')"
        )
        batch.create_index("ix_support_tickets_ai_state_updated", ["ai_state", "updated_at"])

    with op.batch_alter_table("support_messages") as batch:
        batch.add_column(
            sa.Column("author_kind", sa.String(length=16), server_default="human", nullable=False)
        )
        batch.add_column(sa.Column("ai_reply_to_seq", sa.Integer(), nullable=True))
        batch.alter_column("author_id", existing_type=sa.Uuid(), nullable=True)
        batch.create_check_constraint(
            op.f("ck_support_messages_author"),
            "(author_kind = 'human' AND author_id IS NOT NULL AND ai_reply_to_seq IS NULL)"
            " OR (author_kind = 'assistant' AND author_id IS NULL AND ai_reply_to_seq IS NOT NULL)",
        )
        batch.create_unique_constraint(
            op.f("uq_support_messages_ticket_id_ai_reply_to_seq"), ["ticket_id", "ai_reply_to_seq"]
        )


def downgrade() -> None:
    # Assistant replies have no human author; the older schema cannot hold them.
    op.execute("DELETE FROM support_messages WHERE author_kind = 'assistant'")
    with op.batch_alter_table("support_messages") as batch:
        batch.drop_constraint(op.f("uq_support_messages_ticket_id_ai_reply_to_seq"), type_="unique")
        batch.drop_constraint(op.f("ck_support_messages_author"), type_="check")
        batch.alter_column("author_id", existing_type=sa.Uuid(), nullable=False)
        batch.drop_column("ai_reply_to_seq")
        batch.drop_column("author_kind")

    with op.batch_alter_table("support_tickets") as batch:
        batch.drop_index("ix_support_tickets_ai_state_updated")
        batch.drop_constraint(op.f("ck_support_tickets_ai_state"), type_="check")
        batch.drop_constraint(op.f("ck_support_tickets_support_mode"), type_="check")
        batch.drop_column("ai_started_at")
        batch.drop_column("ai_source_seq")
        batch.drop_column("ai_state")
        batch.drop_column("support_mode")
