"""users: Google accounts with google_sub and email, password optional

Revision ID: a7c41e9d3b58
Revises: 80db0ba7c3f3
Create Date: 2026-11-03 20:00:00.000000+00:00

Only ``users`` changes; existing accounts keep their password and get NULL
``google_sub``/``email``. Nothing is linked by email. SQLite rebuilds the table
in batch mode. Downgrade is lossy: Google accounts keep their rows with the
unusable password hash ``!`` (password login fails for them).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c41e9d3b58"
down_revision: str | Sequence[str] | None = "80db0ba7c3f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HAS_CREDENTIALS = "ck_users_has_credentials"
GOOGLE_SUB_UNIQUE = "uq_users_google_sub"
UNUSABLE_PASSWORD_HASH = "!"

users = sa.table("users", sa.column("password_hash", sa.String()))


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=320), nullable=True))
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
        batch_op.create_unique_constraint(op.f(GOOGLE_SUB_UNIQUE), ["google_sub"])
        batch_op.create_check_constraint(
            op.f(HAS_CREDENTIALS), "password_hash IS NOT NULL OR google_sub IS NOT NULL"
        )


def downgrade() -> None:
    op.execute(
        users.update()
        .where(users.c.password_hash.is_(None))
        .values(password_hash=UNUSABLE_PASSWORD_HASH)
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(op.f(HAS_CREDENTIALS), type_="check")
        batch_op.drop_constraint(op.f(GOOGLE_SUB_UNIQUE), type_="unique")
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column("email")
        batch_op.drop_column("google_sub")
