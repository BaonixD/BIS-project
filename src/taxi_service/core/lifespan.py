import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taxi_service.core.config import Settings
from taxi_service.core.logging import configure_logging
from taxi_service.database.migrations import expected_heads
from taxi_service.database.session import create_database_engine, create_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Acquire application resources on startup and release them on shutdown.

    Sets ``app.state.engine``, ``app.state.session_factory`` and
    ``app.state.migration_heads``. Never runs migrations or seed; those are
    separate commands. Connecting is lazy: startup succeeds without a database.
    """
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    engine = create_database_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.migration_heads = expected_heads()
    logger.info("Application started")
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("Application stopped")
