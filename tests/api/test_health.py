import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from taxi_service.core.config import Settings
from taxi_service.database import readiness
from taxi_service.database.migrations import expected_heads
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.main import create_app


@asynccontextmanager
async def serve(database_url: str) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    """App on ``database_url`` with its lifespan running, and a client for it."""
    app = create_app(Settings(_env_file=None, database_url=database_url))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield app, client


async def get_ready(database_url: str) -> httpx.Response:
    async with serve(database_url) as (_, client):
        return await client.get("/health/ready")


def assert_not_ready(response: httpx.Response, code: str) -> dict[str, Any]:
    assert response.status_code == 503
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    assert body["error"]["details"] == {}
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


async def test_live_reports_running_process(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_when_database_answers_and_is_at_head(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_not_ready_when_database_was_never_migrated(empty_database_url: str) -> None:
    response = await get_ready(empty_database_url)

    assert_not_ready(response, "database_not_migrated")


async def test_not_ready_when_database_revision_is_not_head(
    session_factory: SessionFactory, database_url: str
) -> None:
    async with session_factory.begin() as session:
        await session.execute(text("UPDATE alembic_version SET version_num = '0000aaaa0000'"))

    response = await get_ready(database_url)

    assert_not_ready(response, "database_not_migrated")


async def test_not_ready_when_database_is_unreachable(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-directory" / "unreachable-test.db"

    response = await get_ready(f"sqlite+aiosqlite:///{missing}")

    assert_not_ready(response, "database_unavailable")
    assert "no-such-directory" not in response.text
    assert "sqlite" not in response.text.lower()


async def test_not_ready_when_database_file_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing-test.db"

    response = await get_ready(f"sqlite+aiosqlite:///{missing}")

    assert_not_ready(response, "database_unavailable")
    assert not await asyncio.to_thread(missing.exists)


async def test_not_ready_when_database_check_times_out(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def hanging_revisions(connection: AsyncConnection) -> frozenset[str]:
        await asyncio.sleep(1)
        return expected_heads()

    monkeypatch.setattr(readiness, "READINESS_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(readiness, "current_revisions", hanging_revisions)

    response = await get_ready(database_url)

    assert_not_ready(response, "database_unavailable")


async def test_readiness_is_not_blocked_by_open_write_transaction(
    session_factory: SessionFactory, database_url: str
) -> None:
    events: list[str] = []
    writer_holds_lock = asyncio.Event()
    checked = asyncio.Event()

    async def writer() -> None:
        async with session_factory.begin() as session:
            await session.execute(text("CREATE TABLE busy (id INTEGER PRIMARY KEY)"))
            writer_holds_lock.set()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(checked.wait(), 1.0)
            events.append("writer released")

    async def probe() -> None:
        await writer_holds_lock.wait()
        response = await get_ready(database_url)
        events.append(f"ready {response.status_code}")
        checked.set()

    await asyncio.gather(writer(), probe())

    assert events == ["ready 200", "writer released"]


async def test_readiness_does_not_create_schema(empty_database_url: str) -> None:
    await get_ready(empty_database_url)

    assert await tables_in(empty_database_url) == []


async def tables_in(database_url: str) -> list[str]:
    async with (
        serve(database_url) as (app, _),
        app.state.session_factory() as session,
        read_transaction(session),
    ):
        result = await session.scalars(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        return list(result)


async def test_app_uses_the_test_database(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    async with session_factory.begin() as session:
        await session.execute(text("CREATE TABLE shared_probe (id INTEGER PRIMARY KEY)"))
        await session.execute(text("INSERT INTO shared_probe (id) VALUES (7)"))

    async with app.state.session_factory() as session, read_transaction(session):
        assert await session.scalar(text("SELECT id FROM shared_probe")) == 7


async def test_lifespan_disposes_engine_on_shutdown(database_url: str) -> None:
    async with serve(database_url) as (app, client):
        await client.get("/health/ready")
        engine = app.state.engine
        assert engine.pool.checkedin() == 1

    assert engine.pool.checkedin() == 0
