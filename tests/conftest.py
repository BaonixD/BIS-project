from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from taxi_service.core.config import Settings
from taxi_service.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app(Settings(_env_file=None))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
