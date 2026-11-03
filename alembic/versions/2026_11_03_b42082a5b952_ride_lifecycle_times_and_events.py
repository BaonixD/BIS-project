"""rides: lifecycle stage times and cancel reason; ride_events history

Revision ID: b42082a5b952
Revises: 5d2e4cb65b5e
Create Date: 2026-11-03 12:00:00.000000+00:00

The new rides columns are nullable: existing rides keep NULL (their history is
unknown). Adding them needs no table rebuild on SQLite; the downgrade rebuilds
rides in batch mode and keeps its CHECK constraints and partial indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b42082a5b952"
down_revision: str | Sequence[str] | None = "5d2e4cb65b5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGE_TIMES = ("assigned_at", "arrived_at", "started_at", "completed_at", "cancelled_at")
STATUSES = (
    "'arrived', 'assigned', 'cancelled', 'completed', 'in_progress', 'no_driver', 'searching'"
)
COMMANDS = "'arrive', 'assign', 'cancel', 'complete', 'mark_no_driver', 'release', 'start'"


def upgrade() -> None:
    with op.batch_alter_table("rides") as batch_op:
        for column in STAGE_TIMES:
            batch_op.add_column(sa.Column(column, sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancel_reason", sa.String(length=200), nullable=True))
    op.create_table(
        "ride_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("command", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"from_status IN ({STATUSES})", name=op.f("ck_ride_events_from_status")),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name=op.f("ck_ride_events_to_status")),
        sa.CheckConstraint(f"command IN ({COMMANDS})", name=op.f("ck_ride_events_command")),
        sa.CheckConstraint(
            "reason IS NULL OR length(reason) BETWEEN 1 AND 200",
            name=op.f("ck_ride_events_reason_length"),
        ),
        sa.ForeignKeyConstraint(
            ["ride_id"], ["rides.id"], name=op.f("fk_ride_events_ride_id_rides")
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_ride_events_actor_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_events")),
    )
    op.create_index(
        "ix_ride_events_ride_id_created_at", "ride_events", ["ride_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ride_events_ride_id_created_at", table_name="ride_events")
    op.drop_table("ride_events")
    with op.batch_alter_table("rides") as batch_op:
        batch_op.drop_column("cancel_reason")
        for column in reversed(STAGE_TIMES):
            batch_op.drop_column(column)
