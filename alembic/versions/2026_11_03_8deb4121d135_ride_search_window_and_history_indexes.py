"""rides: driver search window, history indexes and the searching index

Revision ID: 8deb4121d135
Revises: 640cf8e50671
Create Date: 2026-11-03 10:00:00.000000+00:00

Existing rides get the window ``created_at`` .. ``created_at + 180 s``
(MVP_SPEC §6) before the columns become NOT NULL.
"""

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa
from alembic import op

revision: str = "8deb4121d135"
down_revision: str | Sequence[str] | None = "640cf8e50671"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCHING = "status = 'searching'"
SEARCH_BUDGET = timedelta(seconds=180)


def backfill_search_window() -> None:
    rides = sa.table(
        "rides",
        sa.column("id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("search_started_at", sa.DateTime(timezone=True)),
        sa.column("search_deadline", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    for ride_id, created_at in connection.execute(sa.select(rides.c.id, rides.c.created_at)):
        connection.execute(
            rides.update()
            .where(rides.c.id == ride_id)
            .values(search_started_at=created_at, search_deadline=created_at + SEARCH_BUDGET)
        )


def upgrade() -> None:
    with op.batch_alter_table("rides") as batch_op:
        batch_op.add_column(sa.Column("search_started_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("search_deadline", sa.DateTime(timezone=True)))
    backfill_search_window()
    with op.batch_alter_table("rides") as batch_op:
        for column in ("search_started_at", "search_deadline"):
            batch_op.alter_column(column, existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.create_check_constraint(
            op.f("ck_rides_search_deadline_after_start"), "search_deadline > search_started_at"
        )
    op.create_index("ix_rides_passenger_id_created_at", "rides", ["passenger_id", "created_at"])
    op.create_index("ix_rides_driver_id_created_at", "rides", ["driver_id", "created_at"])
    op.create_index(
        "ix_rides_searching_search_deadline",
        "rides",
        ["search_deadline"],
        sqlite_where=sa.text(SEARCHING),
        postgresql_where=sa.text(SEARCHING),
    )


def downgrade() -> None:
    op.drop_index("ix_rides_searching_search_deadline", table_name="rides")
    op.drop_index("ix_rides_driver_id_created_at", table_name="rides")
    op.drop_index("ix_rides_passenger_id_created_at", table_name="rides")
    with op.batch_alter_table("rides") as batch_op:
        batch_op.drop_constraint(op.f("ck_rides_search_deadline_after_start"), type_="check")
        batch_op.drop_column("search_deadline")
        batch_op.drop_column("search_started_at")
