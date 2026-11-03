import asyncio
import logging
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.database.migrations import current_revisions
from taxi_service.database.session import read_connection
from taxi_service.database.sqlite import sqlite_file_missing

logger = logging.getLogger(__name__)

READINESS_TIMEOUT_SECONDS = 2.0


class DatabaseReadiness(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"
    NOT_MIGRATED = "not_migrated"


async def check_database(engine: AsyncEngine, heads: frozenset[str]) -> DatabaseReadiness:
    """Whether the database answers and its schema is exactly at the Alembic ``heads``.

    Runs on the read path within ``READINESS_TIMEOUT_SECONDS``. A missing SQLite
    file is reported as unavailable without connecting, so no file is created.
    """
    if await asyncio.to_thread(sqlite_file_missing, engine.url):
        logger.warning("Database file does not exist")
        return DatabaseReadiness.UNAVAILABLE
    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            revisions = await _read_revisions(engine)
    except TimeoutError:
        logger.warning("Database readiness check timed out")
        return DatabaseReadiness.UNAVAILABLE
    except (SQLAlchemyError, OSError):
        logger.warning("Database readiness check failed", exc_info=True)
        return DatabaseReadiness.UNAVAILABLE
    if not heads or revisions != heads:
        return DatabaseReadiness.NOT_MIGRATED
    return DatabaseReadiness.READY


async def _read_revisions(engine: AsyncEngine) -> frozenset[str]:
    async with read_connection(engine) as connection:
        await connection.execute(text("SELECT 1"))
        return await current_revisions(connection)
