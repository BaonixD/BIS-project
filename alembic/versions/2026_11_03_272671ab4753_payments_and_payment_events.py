"""payments: one manual-verification payment per ride; payment_events audit history

Revision ID: 272671ab4753
Revises: b42082a5b952
Create Date: 2026-11-03 14:00:00.000000+00:00

New tables only; rides is not rebuilt. Rides completed before this revision
get the record a completion opens now (cash, unpaid, the ride's amount, at
``completed_at``) and its ``open`` event, so every completed ride has a
payment. The downgrade drops both tables: payment states and their audit
history are lost (back them up first, see README).
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "272671ab4753"
down_revision: str | Sequence[str] | None = "b42082a5b952"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METHODS = "'cash', 'kaspi_link'"
STATUSES = "'confirmed', 'reported', 'unpaid'"
ACTIONS = "'change_method', 'confirm', 'open', 'report'"
CONFIRMED = "status = 'confirmed'"
KASPI = "method = 'kaspi_link'"


def reference_length(column: str) -> str:
    return f"{column} IS NULL OR length({column}) BETWEEN 1 AND 200"


def upgrade() -> None:
    payments = op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("amount_kzt", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verification", sa.String(length=16), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmation_reference", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_kzt > 0", name=op.f("ck_payments_amount_positive")),
        sa.CheckConstraint("currency = 'KZT'", name=op.f("ck_payments_currency_kzt")),
        sa.CheckConstraint(f"method IN ({METHODS})", name=op.f("ck_payments_method")),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_payments_status")),
        sa.CheckConstraint("verification IN ('manual')", name=op.f("ck_payments_verification")),
        sa.CheckConstraint(
            f"({CONFIRMED} AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)"
            f" OR (NOT ({CONFIRMED}) AND confirmed_at IS NULL AND confirmed_by IS NULL"
            " AND confirmation_reference IS NULL)",
            name=op.f("ck_payments_confirmed_matches_status"),
        ),
        sa.CheckConstraint(
            "(status = 'unpaid' AND reported_at IS NULL)"
            " OR (status = 'reported' AND reported_at IS NOT NULL)"
            f" OR {CONFIRMED}",
            name=op.f("ck_payments_reported_matches_status"),
        ),
        sa.CheckConstraint(
            f"reported_at IS NULL OR {KASPI}", name=op.f("ck_payments_report_only_kaspi")
        ),
        sa.CheckConstraint(
            f"NOT ({CONFIRMED} AND {KASPI}) OR confirmation_reference IS NOT NULL",
            name=op.f("ck_payments_kaspi_confirmation_reference"),
        ),
        sa.CheckConstraint(
            reference_length("confirmation_reference"),
            name=op.f("ck_payments_confirmation_reference_length"),
        ),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], name=op.f("fk_payments_ride_id_rides")),
        sa.ForeignKeyConstraint(
            ["confirmed_by"], ["users.id"], name=op.f("fk_payments_confirmed_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("ride_id", name=op.f("uq_payments_ride_id")),
    )
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
        sa.CheckConstraint(f"action IN ({ACTIONS})", name=op.f("ck_payment_events_action")),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({STATUSES})",
            name=op.f("ck_payment_events_from_status"),
        ),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name=op.f("ck_payment_events_to_status")),
        sa.CheckConstraint(
            f"from_method IS NULL OR from_method IN ({METHODS})",
            name=op.f("ck_payment_events_from_method"),
        ),
        sa.CheckConstraint(f"to_method IN ({METHODS})", name=op.f("ck_payment_events_to_method")),
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
    op.create_index(
        "ix_payment_events_payment_id_created_at",
        "payment_events",
        ["payment_id", "created_at", "id"],
    )
    open_payments_of_completed_rides(payments, events)


def open_payments_of_completed_rides(payments: sa.Table, events: sa.Table) -> None:
    rides = sa.table(
        "rides",
        sa.column("id", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("amount_kzt", sa.Integer()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    completed = op.get_bind().execute(
        sa.select(
            rides.c.id,
            rides.c.amount_kzt,
            sa.func.coalesce(rides.c.completed_at, rides.c.updated_at),
        )
        .where(rides.c.status == "completed")
        .order_by(rides.c.id)
    )
    payment_rows, event_rows = [], []
    for ride_id, amount_kzt, opened_at in completed:
        payment_id = uuid.uuid4()
        payment_rows.append(
            {
                "id": payment_id,
                "ride_id": ride_id,
                "amount_kzt": amount_kzt,
                "currency": "KZT",
                "method": "cash",
                "status": "unpaid",
                "verification": "manual",
                "created_at": opened_at,
                "updated_at": opened_at,
            }
        )
        event_rows.append(
            {
                "id": uuid.uuid4(),
                "payment_id": payment_id,
                "action": "open",
                "to_status": "unpaid",
                "to_method": "cash",
                "created_at": opened_at,
            }
        )
    if payment_rows:
        op.bulk_insert(payments, payment_rows)
        op.bulk_insert(events, event_rows)


def downgrade() -> None:
    op.drop_index("ix_payment_events_payment_id_created_at", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_table("payments")
