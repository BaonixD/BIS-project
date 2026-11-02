import logging
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.database.migrations import current_revisions

logger = logging.getLogger(__name__)

READINESS_TIMEOUT_SECONDS = 2.0


class DatabaseReadiness(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"
    NOT_MIGRATED = "not_migrated"


async def check_database(engine: AsyncEngine, heads: frozenset[str]) -> DatabaseReadiness:
    """Whether the database answers and its schema is exactly at the Alembic ``heads``."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            revisions = await current_revisions(connection)
    except (SQLAlchemyError, OSError):
        logger.warning("Database readiness check failed", exc_info=True)
        return DatabaseReadiness.UNAVAILABLE
    if not heads or revisions != heads:
        return DatabaseReadiness.NOT_MIGRATED
    return DatabaseReadiness.READY
