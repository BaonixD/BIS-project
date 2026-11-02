"""baseline: empty starting point of the migration history

Creates no schema objects. It gives the history a single root head, lets
``alembic_version`` tell a migrated database from a fresh one (readiness),
and is the ``down_revision`` of the first revision with real tables.

Revision ID: dea9719c6061
Revises:
Create Date: 2026-11-02 19:45:12.930189+00:00
"""

from collections.abc import Sequence

revision: str = "dea9719c6061"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
