from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from taxi_service.database.sqlite import READ_ONLY_OPTION, configure_sqlite_engine

SessionFactory = async_sessionmaker[AsyncSession]


def create_database_engine(url: str, *, enforce_foreign_keys: bool = True) -> AsyncEngine:
    """Create the application engine; the caller owns it and must ``dispose()`` it.

    SQLite engines get the connection setup described in
    :func:`taxi_service.database.sqlite.configure_sqlite_engine`.
    """
    engine = create_async_engine(url)
    if engine.dialect.name == "sqlite":
        configure_sqlite_engine(engine.sync_engine, enforce_foreign_keys=enforce_foreign_keys)
    return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Sessions without autobegin that keep loaded attributes after commit.

    A statement outside ``session.begin()`` or :func:`read_transaction` raises
    instead of silently opening a transaction that would hold the SQLite lock
    until the session closes.
    """
    return async_sessionmaker(engine, expire_on_commit=False, autobegin=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a new session per request from ``app.state.session_factory``.

    It never commits and never begins. Rules for every use:

    - router or auth dependency: a short ``async with read_transaction(session):``;
    - service: one ``async with session.begin():`` around the whole operation
      (reads that decide a write belong inside it);
    - never await external HTTP or other slow I/O inside a transaction.
    """
    session_factory: SessionFactory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def read_transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Short read-only transaction: ``async with read_transaction(session):``.

    On SQLite it begins DEFERRED with ``query_only``, so it does not wait for
    writers and any write inside raises ``OperationalError``. Reads whose result
    decides a following write belong in ``session.begin()`` instead. On other
    databases it is an ordinary transaction.
    """
    async with session.begin():
        await session.connection(execution_options={READ_ONLY_OPTION: True})
        yield session
