"""Shared fixtures: one disposable, migrated SQLite file per test.

Alembic migrates a template database once per session; each test gets its own
copy under ``tmp_path``. Sessions commit for real, so concurrency tests can use
several independent sessions from ``session_factory``.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.core.config import Settings
from taxi_service.database.migrations import alembic_config
from taxi_service.database.safety import remove_sqlite_database, replace_sqlite_database
from taxi_service.database.session import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from taxi_service.main import create_app


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture(autouse=True)
def _no_ambient_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # A DATABASE_URL exported in the developer's shell must never reach a test.
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture(scope="session")
def temp_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Only files below this directory may be deleted or overwritten by fixtures."""
    return tmp_path_factory.getbasetemp()


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("template") / "template-test.db"
    command.upgrade(alembic_config(sqlite_url(path), configure_logging=False), "head")
    # Copying only the main file is complete once the WAL is checkpointed (empty).
    wal = path.with_name(path.name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    return path


@pytest.fixture
def empty_database_url(tmp_path: Path, temp_root: Path) -> Iterator[str]:
    """URL of a database file that does not exist yet (never migrated)."""
    url = sqlite_url(tmp_path / "empty-test.db")
    yield url
    remove_sqlite_database(url, temp_root=temp_root)


@pytest.fixture
def database_url(tmp_path: Path, temp_root: Path, migrated_template: Path) -> Iterator[str]:
    """URL of this test's own copy of the migrated template database."""
    url = sqlite_url(tmp_path / "test.db")
    replace_sqlite_database(migrated_template, url, temp_root=temp_root)
    yield url
    remove_sqlite_database(url, temp_root=temp_root)


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> SessionFactory:
    """Every session it opens has its own connection and really commits."""
    return create_session_factory(engine)


@pytest.fixture
def app(database_url: str) -> FastAPI:
    return create_app(Settings(_env_file=None, database_url=database_url))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client for ``app`` with its lifespan (engine startup and disposal) running."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
