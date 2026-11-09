"""Driver working tariffs, preserving legacy eligibility.

Revision ID: a3267d91e0b4
Revises: c6f8a4d219e0
"""

import sqlalchemy as sa
from alembic import op

revision = "a3267d91e0b4"
down_revision = "c6f8a4d219e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_categories",
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("tariff", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "tariff IN ('business', 'comfort', 'comfort_plus', 'economy')",
            name=op.f("ck_vehicle_categories_tariff"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            ondelete="CASCADE",
            name=op.f("fk_vehicle_categories_vehicle_id_vehicles"),
        ),
        sa.PrimaryKeyConstraint("vehicle_id", "tariff", name=op.f("pk_vehicle_categories")),
    )
    # Keep every previously eligible tariff, rather than only the highest class.
    op.execute(
        "INSERT INTO vehicle_categories (vehicle_id, tariff) SELECT id, 'economy' FROM vehicles"
    )
    op.execute(
        "INSERT INTO vehicle_categories (vehicle_id, tariff) SELECT id, 'comfort' FROM vehicles "
        "WHERE car_class IN ('comfort', 'comfort_plus', 'business')"
    )
    op.execute(
        "INSERT INTO vehicle_categories (vehicle_id, tariff) SELECT id, 'comfort_plus' "
        "FROM vehicles "
        "WHERE car_class IN ('comfort_plus', 'business')"
    )
    op.execute(
        "INSERT INTO vehicle_categories (vehicle_id, tariff) SELECT id, 'business' FROM vehicles "
        "WHERE car_class = 'business'"
    )


def downgrade() -> None:
    op.drop_table("vehicle_categories")
