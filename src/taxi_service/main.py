from fastapi import FastAPI

from taxi_service.api.exception_handlers import register_exception_handlers
from taxi_service.api.router import api_router
from taxi_service.core.config import Settings
from taxi_service.core.request_id import RequestIdMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Mini Taxi Service", version="0.1.0")
    app.state.settings = settings or Settings()
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
