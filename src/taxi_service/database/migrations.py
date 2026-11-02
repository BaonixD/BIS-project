"""Alembic integration: configuration, expected head and the current revision."""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def alembic_config(database_url: str | None = None, *, configure_logging: bool = True) -> Config:
    """Alembic configuration of this project.

    ``database_url`` overrides ``DATABASE_URL``; tests always pass one.
    ``configure_logging=False`` keeps the caller's logging configuration.
    """
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    config.attributes["configure_logging"] = configure_logging
    return config


def expected_heads(config: Config | None = None) -> frozenset[str]:
    """Head revisions of the migration scripts (reads files, no database access)."""
    script = ScriptDirectory.from_config(config or alembic_config())
    return frozenset(script.get_heads())


async def current_revisions(connection: AsyncConnection) -> frozenset[str]:
    """Revisions recorded in ``alembic_version``; empty if never migrated."""
    return await connection.run_sync(_current_revisions)


def _current_revisions(connection: Connection) -> frozenset[str]:
    return frozenset(MigrationContext.configure(connection).get_current_heads())
