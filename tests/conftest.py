"""Shared fixtures: one disposable, migrated SQLite file per test.

Alembic migrates a template database once per session; each test gets its own
copy under ``tmp_path``. Sessions commit for real, so concurrency tests can use
several independent sessions from ``session_factory``.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.rides import PICKUP, RideFactory
from support.routing import FakeRoutingProvider, isolate_routing_environment
from taxi_service.core.config import Settings
from taxi_service.database.migrations import alembic_config
from taxi_service.database.safety import remove_sqlite_database, replace_sqlite_database
from taxi_service.database.session import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from taxi_service.main import create_app
from taxi_service.modules.auth.passwords import PasswordHasher


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture(autouse=True)
def _no_ambient_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # A DATABASE_URL exported in the developer's shell must never reach a test.
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture(autouse=True)
def _no_dispatch_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Applications built in tests run no background dispatch loop unless a test
    # enables it (tests/api/test_dispatch_loop.py); tests call dispatch directly.
    monkeypatch.setenv("DISPATCH_LOOP_ENABLED", "false")


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
    """URL of an existing but empty database file (never migrated)."""
    path = tmp_path / "empty-test.db"
    path.touch()  # a zero-byte file is a valid, empty SQLite database
    url = sqlite_url(path)
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
def clock() -> ManualClock:
    """The application's clock in API tests; move it with ``clock.advance(...)``."""
    return ManualClock()


TEST_BASE_URL = "https://testserver"


@pytest.fixture
def settings(database_url: str) -> Settings:
    """Secure defaults (Secure cookie, empty CORS allowlist) except hashing cost.

    Argon2id runs at its minimum cost: hashing stays real but takes microseconds.
    """
    return Settings(
        _env_file=None,
        database_url=database_url,
        password_hash_time_cost=1,
        password_hash_memory_kib=8,
        password_hash_parallelism=1,
    )


@pytest.fixture(autouse=True)
def _isolated_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_routing_environment(monkeypatch)


@pytest.fixture
def routing_provider() -> FakeRoutingProvider:
    """Deterministic routes; tests inspect ``calls`` or use ``fail_with``."""
    return FakeRoutingProvider()


@pytest.fixture
def app(settings: Settings, clock: ManualClock, routing_provider: FakeRoutingProvider) -> FastAPI:
    return create_app(settings, clock=clock, routing_provider=routing_provider)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client for ``app`` with its lifespan (engine startup and disposal) running.

    The base URL is HTTPS so the cookie jar returns the ``Secure`` session cookie,
    as a browser would; ``support.auth`` has helpers to register and log in.
    """
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=TEST_BASE_URL) as client:
            yield client


@pytest.fixture
def driver_factory(
    session_factory: SessionFactory, clock: ManualClock, settings: Settings
) -> DriverFactory:
    """Drivers (and their approving admin) created directly through the services."""
    return DriverFactory(session_factory, clock, PasswordHasher.from_settings(settings))


@pytest.fixture
def ride_factory(
    session_factory: SessionFactory, clock: ManualClock, settings: Settings
) -> RideFactory:
    """Passengers and searching rides created directly through the services."""
    return RideFactory(session_factory, clock, PasswordHasher.from_settings(settings))


@pytest.fixture
def dispatcher(session_factory: SessionFactory, clock: ManualClock) -> Dispatcher:
    """Dispatch service calls on their own sessions, with the test clock and default policy."""
    return Dispatcher(session_factory, clock)


@pytest.fixture
async def available_driver(driver_factory: DriverFactory) -> uuid.UUID:
    """An approved, online driver next to the default pickup (``support.rides.ABAY_DOSTYK``).

    With it a ride ordered through the API stays ``searching`` with a pending
    offer; without any driver dispatch ends the search at once (``no_driver``).
    """
    return await driver_factory.driver("available_driver", location=PICKUP)
