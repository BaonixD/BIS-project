from fastapi import FastAPI

from taxi_service.api.exception_handlers import register_exception_handlers
from taxi_service.api.router import api_router
from taxi_service.core.clock import Clock, SystemClock
from taxi_service.core.config import Settings
from taxi_service.core.lifespan import lifespan
from taxi_service.core.request_id import RequestIdMiddleware
from taxi_service.modules.auth.passwords import PasswordHasher


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    app = FastAPI(title="Mini Taxi Service", version="0.1.0", lifespan=lifespan)
    settings = settings or Settings()
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.password_hasher = PasswordHasher.from_settings(settings)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
