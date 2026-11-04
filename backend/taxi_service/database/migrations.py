from pathlib import Path
from typing import Literal

from alembic.autogenerate.api import AutogenContext
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from taxi_service.database.base import UtcDateTime

# Works only from the source tree (editable install).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def alembic_config(database_url: str | None = None, *, configure_logging: bool = True) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    config.attributes["configure_logging"] = configure_logging
    return config


def expected_heads(config: Config | None = None) -> frozenset[str]:
    script = ScriptDirectory.from_config(config or alembic_config())
    return frozenset(script.get_heads())


def render_item(type_: str, obj: object, autogen_context: AutogenContext) -> str | Literal[False]:
    # Migrations must not import application types.
    if type_ == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime(timezone=True)"
    return False


async def current_revisions(connection: AsyncConnection) -> frozenset[str]:
    return await connection.run_sync(_current_revisions)


def _current_revisions(connection: Connection) -> frozenset[str]:
    return frozenset(MigrationContext.configure(connection).get_current_heads())
