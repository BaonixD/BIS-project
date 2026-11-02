from fastapi import FastAPI

from taxi_service.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Mini Taxi Service", version="0.1.0")
    app.state.settings = settings or Settings()
    return app


app = create_app()
