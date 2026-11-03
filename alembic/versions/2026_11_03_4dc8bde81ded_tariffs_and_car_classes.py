"""tariffs: four quote amounts, rides.tariff and vehicles.car_class (ADR 0012)

Revision ID: 4dc8bde81ded
Revises: a7c41e9d3b58
Create Date: 2026-11-03 22:00:00.000000+00:00

``ride_quotes.amount_kzt`` becomes four amounts, one per tariff. An existing
quote keeps its price as the economy amount (edu-v1 economy equals edu-v2
economy) and gets the other three from the edu-v2 rates copied below; its
``tariff_version`` is not changed. Existing rides and vehicles become
``economy``. SQLite rebuilds the three tables in batch mode. Downgrade keeps
the economy amount of a quote; the tariff of a ride and the class of a car
are dropped (a ride keeps its own ``amount_kzt``).
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "4dc8bde81ded"
down_revision: str | Sequence[str] | None = "a7c41e9d3b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARIFFS = ("economy", "comfort", "comfort_plus", "business")
TARIFF_VALUES = "'business', 'comfort', 'comfort_plus', 'economy'"
AMOUNT_COLUMNS = {tariff: f"{tariff}_amount_kzt" for tariff in TARIFFS}
# edu-v2: base, per km, per minute, minimum (KZT); a copy, not an import of application code.
RATES = {
    "comfort": (700, 160, 25, 1100),
    "comfort_plus": (900, 200, 30, 1500),
    "business": (1200, 260, 40, 2000),
}
AMOUNT_CHECK = "ck_ride_quotes_amount_positive"
OLD_AMOUNT_CONDITION = "amount_kzt > 0"
NEW_AMOUNT_CONDITION = " AND ".join(f"{column} > 0" for column in AMOUNT_COLUMNS.values())

quotes = sa.table(
    "ride_quotes",
    sa.column("id", sa.Uuid()),
    sa.column("distance_m", sa.Integer()),
    sa.column("duration_s", sa.Integer()),
    sa.column("amount_kzt", sa.Integer()),
    *(sa.column(column, sa.Integer()) for column in AMOUNT_COLUMNS.values()),
)


def fare(rates: tuple[int, int, int, int], distance_m: int, duration_s: int) -> int:
    base, per_km, per_minute, minimum = (Decimal(value) for value in rates)
    raw = base + per_km * Decimal(distance_m) / 1000 + per_minute * Decimal(duration_s) / 60
    return int(max(minimum, raw).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def upgrade() -> None:
    with op.batch_alter_table("ride_quotes") as batch_op:
        for column in AMOUNT_COLUMNS.values():
            batch_op.add_column(sa.Column(column, sa.Integer(), nullable=True))
    price_existing_quotes()
    with op.batch_alter_table("ride_quotes") as batch_op:
        batch_op.drop_constraint(op.f(AMOUNT_CHECK), type_="check")
        batch_op.drop_column("amount_kzt")
        for column in AMOUNT_COLUMNS.values():
            batch_op.alter_column(column, existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(op.f(AMOUNT_CHECK), NEW_AMOUNT_CONDITION)
    with op.batch_alter_table("rides") as batch_op:
        batch_op.add_column(
            sa.Column("tariff", sa.String(length=16), server_default="economy", nullable=False)
        )
        batch_op.create_check_constraint(op.f("ck_rides_tariff"), f"tariff IN ({TARIFF_VALUES})")
    with op.batch_alter_table("vehicles") as batch_op:
        batch_op.add_column(
            sa.Column("car_class", sa.String(length=16), server_default="economy", nullable=False)
        )
        batch_op.create_check_constraint(
            op.f("ck_vehicles_car_class"), f"car_class IN ({TARIFF_VALUES})"
        )


def price_existing_quotes() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(quotes.c.id, quotes.c.distance_m, quotes.c.duration_s, quotes.c.amount_kzt)
    ).all()
    for quote_id, distance_m, duration_s, amount_kzt in rows:
        amounts = {AMOUNT_COLUMNS["economy"]: amount_kzt}
        for tariff, rates in RATES.items():
            amounts[AMOUNT_COLUMNS[tariff]] = fare(rates, distance_m, duration_s)
        bind.execute(quotes.update().where(quotes.c.id == quote_id).values(**amounts))


def downgrade() -> None:
    with op.batch_alter_table("vehicles") as batch_op:
        batch_op.drop_constraint(op.f("ck_vehicles_car_class"), type_="check")
        batch_op.drop_column("car_class")
    with op.batch_alter_table("rides") as batch_op:
        batch_op.drop_constraint(op.f("ck_rides_tariff"), type_="check")
        batch_op.drop_column("tariff")
    with op.batch_alter_table("ride_quotes") as batch_op:
        batch_op.add_column(sa.Column("amount_kzt", sa.Integer(), nullable=True))
    op.execute(quotes.update().values(amount_kzt=quotes.c.economy_amount_kzt))
    with op.batch_alter_table("ride_quotes") as batch_op:
        batch_op.drop_constraint(op.f(AMOUNT_CHECK), type_="check")
        for column in AMOUNT_COLUMNS.values():
            batch_op.drop_column(column)
        batch_op.alter_column("amount_kzt", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(op.f(AMOUNT_CHECK), OLD_AMOUNT_CONDITION)
