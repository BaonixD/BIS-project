"""One-container deploy: the API process also serves the built web app (FRONTEND_DIST)."""

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from support.routing import FakeRoutingProvider
from taxi_service.core.config import Settings
from taxi_service.main import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>TulparTaxi</title>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "sw.js").write_text("// worker")
    (tmp_path / "favicon.png").write_bytes(b"png")
    return tmp_path


@pytest.fixture
def app(settings: Settings, dist: Path, routing_provider: FakeRoutingProvider) -> FastAPI:
    return create_app(
        settings.model_copy(update={"frontend_dist": dist}), routing_provider=routing_provider
    )


async def test_client_routes_get_the_app_page(client: httpx.AsyncClient) -> None:
    for path in ("/", "/history/42", "/admin/rides?view=all"):
        response = await client.get(path)
        assert response.status_code == 200, path
        assert "TulparTaxi" in response.text
        assert response.headers["cache-control"] == "no-cache"


async def test_built_files_are_served_with_their_cache_rules(client: httpx.AsyncClient) -> None:
    asset = await client.get("/assets/app-123.js")
    assert asset.text == "console.log(1)"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    worker = await client.get("/sw.js")
    assert worker.headers["cache-control"] == "no-cache"
    assert (await client.get("/favicon.png")).headers["cache-control"] == "public, max-age=3600"


async def test_api_paths_never_fall_back_to_the_page(client: httpx.AsyncClient) -> None:
    missing = await client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")
    assert (await client.get("/health/live")).json()["status"] == "ok"


async def test_files_outside_the_build_are_not_served(
    client: httpx.AsyncClient, dist: Path
) -> None:
    (dist.parent / "secret.txt").write_text("secret")
    response = await client.get("/../secret.txt")
    assert "secret" not in response.text
