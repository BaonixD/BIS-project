"""payments: chosen with the order; refunded status and refunded_at (ADR 0010)

Revision ID: 80db0ba7c3f3
Revises: 4fdb9385a8e5
Create Date: 2026-11-03 20:00:00.000000+00:00

Every ride now has its payment from the order on. Rides without one (those not
completed yet, cancelled or without a driver) get the default: cash, unpaid,
the ride's amount, at the ride's ``created_at``. SQLite rebuilds payments in
batch mode. Downgrade is lossy: only payments of completed rides are kept,
since the previous flow opened a payment at completion only.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "80db0ba7c3f3"
down_revision: str | Sequence[str] | None = "4fdb9385a8e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CHECKS = {
    "ck_payments_status": "status IN ('paid', 'unpaid')",
    "ck_payments_paid_matches_status": (
        "(status = 'unpaid' AND paid_at IS NULL) OR (status = 'paid' AND paid_at IS NOT NULL)"
    ),
}
NEW_CHECKS = {
    "ck_payments_status": "status IN ('paid', 'refunded', 'unpaid')",
    "ck_payments_times_match_status": (
        "(status = 'unpaid' AND paid_at IS NULL AND refunded_at IS NULL)"
        " OR (status = 'paid' AND paid_at IS NOT NULL AND refunded_at IS NULL)"
        " OR (status = 'refunded' AND paid_at IS NOT NULL AND refunded_at IS NOT NULL)"
    ),
}

rides = sa.table(
    "rides",
    sa.column("id", sa.Uuid()),
    sa.column("status", sa.String()),
    sa.column("amount_kzt", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
payments = sa.table(
    "payments",
    sa.column("id", sa.Uuid()),
    sa.column("ride_id", sa.Uuid()),
    sa.column("amount_kzt", sa.Integer()),
    sa.column("currency", sa.String()),
    sa.column("method", sa.String()),
    sa.column("status", sa.String()),
    sa.column("paid_at", sa.DateTime(timezone=True)),
    sa.column("refunded_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        for name in OLD_CHECKS:
            batch_op.drop_constraint(op.f(name), type_="check")
        batch_op.add_column(sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
        for name, condition in NEW_CHECKS.items():
            batch_op.create_check_constraint(op.f(name), condition)
    open_payments_of_rides_without_one()


def open_payments_of_rides_without_one() -> None:
    without_payment = ~sa.exists().where(payments.c.ride_id == rides.c.id)
    rows = op.get_bind().execute(
        sa.select(rides.c.id, rides.c.amount_kzt, rides.c.created_at)
        .where(without_payment)
        .order_by(rides.c.id)
    )
    payment_rows = [
        {
            "id": uuid.uuid4(),
            "ride_id": ride_id,
            "amount_kzt": amount_kzt,
            "currency": "KZT",
            "method": "cash",
            "status": "unpaid",
            "paid_at": None,
            "refunded_at": None,
            "created_at": created_at,
            "updated_at": created_at,
        }
        for ride_id, amount_kzt, created_at in rows
    ]
    if payment_rows:
        op.bulk_insert(payments, payment_rows)


def downgrade() -> None:
    completed = sa.select(rides.c.id).where(rides.c.status == "completed")
    op.execute(payments.delete().where(payments.c.ride_id.not_in(completed)))
    with op.batch_alter_table("payments") as batch_op:
        for name in NEW_CHECKS:
            batch_op.drop_constraint(op.f(name), type_="check")
        batch_op.drop_column("refunded_at")
        for name, condition in OLD_CHECKS.items():
            batch_op.create_check_constraint(op.f(name), condition)
