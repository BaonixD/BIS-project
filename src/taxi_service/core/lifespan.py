import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.core.config import Settings
from taxi_service.core.logging import configure_logging
from taxi_service.database.migrations import expected_heads
from taxi_service.database.session import create_database_engine, create_session_factory
from taxi_service.modules.geo.client import (
    OpenRouteServiceClient,
    RoutingProvider,
    create_routing_http_client,
)
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.rides.dispatch_loop import DispatchLoop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Never runs migrations or seed; startup works without a database or routing key.
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    engine = create_database_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.migration_heads = expected_heads()
    provider, routing_http = _routing_provider(app.state.routing_provider_override)
    app.state.routing_provider = provider
    app.state.routing_http_client = routing_http
    dispatch_loop = _dispatch_loop(app, settings, engine)
    app.state.dispatch_loop = dispatch_loop
    if dispatch_loop is not None:
        dispatch_loop.start()
    logger.info("Application started")
    try:
        yield
    finally:
        if dispatch_loop is not None:
            await dispatch_loop.stop()
        if routing_http is not None:
            await routing_http.aclose()
        await engine.dispose()
        logger.info("Application stopped")


def _dispatch_loop(app: FastAPI, settings: Settings, engine: AsyncEngine) -> DispatchLoop | None:
    if not settings.dispatch_loop_enabled:
        return None
    return DispatchLoop(
        app.state.session_factory,
        app.state.clock,
        app.state.dispatch_policy,
        interval_s=settings.dispatch_interval_s,
        database_url=engine.url,
    )


def _routing_provider(
    override: RoutingProvider | None,
) -> tuple[RoutingProvider, httpx.AsyncClient | None]:
    """The injected provider, or openrouteservice with an HTTP client this app owns."""
    if override is not None:
        return override, None
    routing_settings = RoutingSettings()
    http = create_routing_http_client(routing_settings)
    return OpenRouteServiceClient.from_settings(routing_settings, http), http
