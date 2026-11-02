import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taxi_service.core.config import Settings
from taxi_service.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Acquire application resources on startup and release them on shutdown.

    Never runs migrations or seed; those are separate commands.
    """
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    logger.info("Application started")
    yield
    logger.info("Application stopped")
