"""Passenger bonuses: a wallet, its history and the share of a ride paid with bonuses."""

import sqlalchemy as sa
from alembic import op

revision = "65908231baa0"
down_revision = "313456def5e5"
branch_labels = None
depends_on = None

ONCE_PER_RIDE = "kind IN ('earn', 'return')"


def upgrade() -> None:
    with op.batch_alter_table("rides") as batch:
        batch.add_column(sa.Column("bonus_kzt", sa.Integer(), server_default="0", nullable=False))
        batch.create_check_constraint(
            op.f("ck_rides_bonus_share"), "bonus_kzt >= 0 AND bonus_kzt * 2 <= amount_kzt"
        )

    op.create_table(
        "bonus_wallets",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("balance_kzt", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("balance_kzt >= 0", name=op.f("ck_bonus_wallets_balance")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_bonus_wallets_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_bonus_wallets")),
    )
    op.create_table(
        "bonus_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount_kzt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_kzt > 0", name=op.f("ck_bonus_entries_amount")),
        sa.CheckConstraint("kind IN ('earn','spend','return')", name=op.f("ck_bonus_entries_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_bonus_entries_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["ride_id"], ["rides.id"], name=op.f("fk_bonus_entries_ride_id_rides")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bonus_entries")),
    )
    with op.batch_alter_table("bonus_entries") as batch:
        batch.create_index("ix_bonus_entries_user_created", ["user_id", "created_at"])
        batch.create_index(
            "uq_bonus_entries_ride_kind_once",
            ["ride_id", "kind"],
            unique=True,
            sqlite_where=sa.text(ONCE_PER_RIDE),
            postgresql_where=sa.text(ONCE_PER_RIDE),
        )


def downgrade() -> None:
    op.drop_table("bonus_entries")
    op.drop_table("bonus_wallets")
    with op.batch_alter_table("rides") as batch:
        batch.drop_constraint(op.f("ck_rides_bonus_share"), type_="check")
        batch.drop_column("bonus_kzt")
