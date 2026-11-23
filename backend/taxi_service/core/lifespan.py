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
from taxi_service.modules.geo.cache import CachedRoutingProvider
from taxi_service.modules.geo.client import RoutingProvider, create_routing_http_client
from taxi_service.modules.geo.config import RoutingSettings
from taxi_service.modules.geo.providers import create_routing_provider
from taxi_service.modules.rides.dispatch_loop import DispatchLoop
from taxi_service.modules.rides.estimates import EstimateCache
from taxi_service.modules.support.ai_client import (
    GeminiProvider,
    SupportAIProvider,
    create_gemini_http_client,
)
from taxi_service.modules.support.ai_config import SupportAISettings
from taxi_service.modules.support.ai_loop import SupportAILoop

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
    app.state.estimate_cache = EstimateCache()
    app.state.routing_provider = provider
    app.state.routing_http_client = routing_http
    dispatch_loop = _dispatch_loop(app, settings, engine)
    app.state.dispatch_loop = dispatch_loop
    if dispatch_loop is not None:
        dispatch_loop.start()
    support_ai_loop, support_ai_http = _support_ai_loop(app, engine)
    app.state.support_ai_loop = support_ai_loop
    if support_ai_loop is not None:
        support_ai_loop.start()
    logger.info("Application started")
    try:
        yield
    finally:
        if support_ai_loop is not None:
            await support_ai_loop.stop()
        if support_ai_http is not None:
            await support_ai_http.aclose()
        if dispatch_loop is not None:
            await dispatch_loop.stop()
        await app.state.estimate_cache.close()
        if isinstance(provider, CachedRoutingProvider):
            await provider.aclose()
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


def _support_ai_loop(
    app: FastAPI, engine: AsyncEngine
) -> tuple[SupportAILoop | None, httpx.AsyncClient | None]:
    """The assistant loop when SUPPORT_AI_ENABLED and a key are set; else ordinary support."""
    settings: SupportAISettings = app.state.support_ai_settings
    if not settings.active:
        logger.info("Support AI is off")
        return None, None
    provider: SupportAIProvider | None = app.state.support_ai_provider_override
    http = None
    if provider is None:
        http = create_gemini_http_client(settings)
        provider = GeminiProvider(settings, http)
    loop = SupportAILoop(
        app.state.session_factory,
        app.state.clock,
        settings,
        provider,
        database_url=engine.url,
    )
    logger.info("Support AI is on, model %s", settings.model)
    return loop, http


def _routing_provider(
    override: RoutingProvider | None,
) -> tuple[RoutingProvider, httpx.AsyncClient | None]:
    """The injected provider, or the configured one with an HTTP client this app owns."""
    if override is not None:
        return override, None
    routing_settings = RoutingSettings()
    http = create_routing_http_client(routing_settings)
    return create_routing_provider(routing_settings, http), http
