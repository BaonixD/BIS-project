"""payments: unpaid or paid with paid_at; drop manual verification and payment_events

Revision ID: 4fdb9385a8e5
Revises: 272671ab4753
Create Date: 2026-11-03 18:00:00.000000+00:00

The owner's simple payments: the passenger's "Paid" counts at once. ``confirmed``
becomes ``paid`` at ``confirmed_at``, ``reported`` becomes ``paid`` at
``reported_at``; ``unpaid`` stays. The audit table and the confirmation columns
are dropped (back them up first, see README). SQLite rebuilds payments in batch mode.
Downgrade is lossy: every payment returns as ``unpaid`` with one ``open`` event.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4fdb9385a8e5"
down_revision: str | Sequence[str] | None = "272671ab4753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENTS_INDEX = "ix_payment_events_payment_id_created_at"
OLD_METHODS = "'cash', 'kaspi_link'"
OLD_STATUSES = "'confirmed', 'reported', 'unpaid'"
OLD_ACTIONS = "'change_method', 'confirm', 'open', 'report'"
CONFIRMED = "status = 'confirmed'"
KASPI = "method = 'kaspi_link'"
CONFIRMATION_COLUMNS = (
    "verification",
    "reported_at",
    "confirmed_at",
    "confirmed_by",
    "confirmation_reference",
)


def reference_length(column: str) -> str:
    return f"{column} IS NULL OR length({column}) BETWEEN 1 AND 200"


OLD_CHECKS = {
    "ck_payments_status": f"status IN ({OLD_STATUSES})",
    "ck_payments_verification": "verification IN ('manual')",
    "ck_payments_confirmed_matches_status": (
        f"({CONFIRMED} AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)"
        f" OR (NOT ({CONFIRMED}) AND confirmed_at IS NULL AND confirmed_by IS NULL"
        " AND confirmation_reference IS NULL)"
    ),
    "ck_payments_reported_matches_status": (
        "(status = 'unpaid' AND reported_at IS NULL)"
        " OR (status = 'reported' AND reported_at IS NOT NULL)"
        f" OR {CONFIRMED}"
    ),
    "ck_payments_report_only_kaspi": f"reported_at IS NULL OR {KASPI}",
    "ck_payments_kaspi_confirmation_reference": (
        f"NOT ({CONFIRMED} AND {KASPI}) OR confirmation_reference IS NOT NULL"
    ),
    "ck_payments_confirmation_reference_length": reference_length("confirmation_reference"),
}
NEW_CHECKS = {
    "ck_payments_status": "status IN ('paid', 'unpaid')",
    "ck_payments_paid_matches_status": (
        "(status = 'unpaid' AND paid_at IS NULL) OR (status = 'paid' AND paid_at IS NOT NULL)"
    ),
}

payments = sa.table(
    "payments",
    sa.column("id", sa.Uuid()),
    sa.column("method", sa.String()),
    sa.column("status", sa.String()),
    sa.column("verification", sa.String()),
    sa.column("paid_at", sa.DateTime(timezone=True)),
    sa.column("reported_at", sa.DateTime(timezone=True)),
    sa.column("confirmed_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.drop_index(EVENTS_INDEX, table_name="payment_events")
    op.drop_table("payment_events")
    with op.batch_alter_table("payments") as batch_op:
        for name in OLD_CHECKS:
            batch_op.drop_constraint(op.f(name), type_="check")
        batch_op.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    settled = payments.c.status.in_(("confirmed", "reported"))
    op.execute(
        payments.update()
        .where(settled)
        .values(
            status="paid",
            paid_at=sa.case(
                (payments.c.status == "confirmed", payments.c.confirmed_at),
                else_=payments.c.reported_at,
            ),
        )
    )
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint(op.f("fk_payments_confirmed_by_users"), type_="foreignkey")
        for column in CONFIRMATION_COLUMNS:
            batch_op.drop_column(column)
        for name, condition in NEW_CHECKS.items():
            batch_op.create_check_constraint(op.f(name), condition)


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        for name in NEW_CHECKS:
            batch_op.drop_constraint(op.f(name), type_="check")
        batch_op.add_column(sa.Column("verification", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("confirmed_by", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("confirmation_reference", sa.String(length=200), nullable=True)
        )
    op.execute(payments.update().values(status="unpaid", verification="manual"))
    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column("verification", existing_type=sa.String(length=16), nullable=False)
        batch_op.drop_column("paid_at")
        batch_op.create_foreign_key(
            op.f("fk_payments_confirmed_by_users"), "users", ["confirmed_by"], ["id"]
        )
        for name, condition in OLD_CHECKS.items():
            batch_op.create_check_constraint(op.f(name), condition)
    events = create_payment_events()
    open_events_of_payments(events)


def create_payment_events() -> sa.Table:
    events = op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("from_method", sa.String(length=16), nullable=True),
        sa.Column("to_method", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"action IN ({OLD_ACTIONS})", name=op.f("ck_payment_events_action")),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({OLD_STATUSES})",
            name=op.f("ck_payment_events_from_status"),
        ),
        sa.CheckConstraint(
            f"to_status IN ({OLD_STATUSES})", name=op.f("ck_payment_events_to_status")
        ),
        sa.CheckConstraint(
            f"from_method IS NULL OR from_method IN ({OLD_METHODS})",
            name=op.f("ck_payment_events_from_method"),
        ),
        sa.CheckConstraint(
            f"to_method IN ({OLD_METHODS})", name=op.f("ck_payment_events_to_method")
        ),
        sa.CheckConstraint(
            "(action = 'open' AND from_status IS NULL AND from_method IS NULL)"
            " OR (action <> 'open' AND from_status IS NOT NULL AND from_method IS NOT NULL)",
            name=op.f("ck_payment_events_previous_state"),
        ),
        sa.CheckConstraint(
            "reference IS NULL OR action = 'confirm'",
            name=op.f("ck_payment_events_reference_only_confirm"),
        ),
        sa.CheckConstraint(
            reference_length("reference"), name=op.f("ck_payment_events_reference_length")
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"], ["payments.id"], name=op.f("fk_payment_events_payment_id_payments")
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_payment_events_actor_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
    )
    op.create_index(EVENTS_INDEX, "payment_events", ["payment_id", "created_at", "id"])
    return events


def open_events_of_payments(events: sa.Table) -> None:
    rows = op.get_bind().execute(
        sa.select(payments.c.id, payments.c.method, payments.c.created_at).order_by(payments.c.id)
    )
    event_rows = [
        {
            "id": uuid.uuid4(),
            "payment_id": payment_id,
            "action": "open",
            "to_status": "unpaid",
            "to_method": method,
            "created_at": created_at,
        }
        for payment_id, method, created_at in rows
    ]
    if event_rows:
        op.bulk_insert(events, event_rows)
