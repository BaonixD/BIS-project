"""Batch migrations that rebuild a referenced SQLite table must keep related rows.

SQLite rebuilds a table as copy -> DROP -> RENAME. With foreign keys enforced,
the DROP deletes the parent rows first and ON DELETE CASCADE removes children.
Throwaway revisions in a temporary directory run through the real env.py.
"""

import asyncio
import os
import textwrap
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from taxi_service.database.migrations import alembic_config, current_revisions, expected_heads
from taxi_service.database.session import create_database_engine

CREATE_TABLES = """
    op.create_table(
        "parent",
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    op.create_table(
        "child",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("parent.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.execute("INSERT INTO parent (id) VALUES (1)")
    op.execute("INSERT INTO child (id, parent_id) VALUES (10, 1)")
"""

REBUILD_PARENT = """
    with op.batch_alter_table("parent", recreate="always") as batch:
        batch.add_column(sa.Column("note", sa.String(20), nullable=True))
"""

BREAK_REFERENCE = """
    op.execute("DELETE FROM parent")
"""


def write_revision(directory: Path, revision: str, down_revision: str, body: str) -> None:
    source = f'''
import sqlalchemy as sa
from alembic import op

revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade() -> None:
{textwrap.indent(textwrap.dedent(body), "    ")}

def downgrade() -> None:
    pass
'''
    (directory / f"{revision}.py").write_text(source)


@pytest.fixture
def scratch_versions(tmp_path: Path) -> Path:
    directory = tmp_path / "scratch_versions"
    directory.mkdir()
    return directory


@pytest.fixture
def config(tmp_path: Path, scratch_versions: Path) -> Config:
    config = alembic_config(
        f"sqlite+aiosqlite:///{tmp_path / 'rebuild-test.db'}", configure_logging=False
    )
    script_location = config.get_main_option("script_location")
    assert script_location is not None
    project_versions = Path(script_location) / "versions"
    config.set_main_option(
        "version_locations", os.pathsep.join([str(project_versions), str(scratch_versions)])
    )
    return config


def query(config: Config, sql: str) -> tuple[object, frozenset[str]]:
    async def run() -> tuple[object, frozenset[str]]:
        engine = create_database_engine(config.attributes["database_url"])
        try:
            async with engine.connect() as connection:
                return await connection.scalar(text(sql)), await current_revisions(connection)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_rebuilding_referenced_table_keeps_child_rows(
    config: Config, scratch_versions: Path
) -> None:
    [project_head] = expected_heads()
    write_revision(scratch_versions, "scratch_tables", project_head, CREATE_TABLES)
    write_revision(scratch_versions, "scratch_rebuild", "scratch_tables", REBUILD_PARENT)

    command.upgrade(config, "head")

    children, revisions = query(config, "SELECT count(*) FROM child")
    assert revisions == {"scratch_rebuild"}
    assert children == 1


def test_migration_leaving_broken_references_is_rolled_back(
    config: Config, scratch_versions: Path
) -> None:
    [project_head] = expected_heads()
    write_revision(scratch_versions, "scratch_tables", project_head, CREATE_TABLES)
    command.upgrade(config, "head")
    write_revision(scratch_versions, "scratch_break", "scratch_tables", BREAK_REFERENCE)

    with pytest.raises(RuntimeError, match="foreign key"):
        command.upgrade(config, "head")

    parents, revisions = query(config, "SELECT count(*) FROM parent")
    assert revisions == {"scratch_tables"}
    assert parents == 1
