from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from taxi_service.database.sqlite import READ_ONLY_OPTION, configure_sqlite_engine

SessionFactory = async_sessionmaker[AsyncSession]


def create_database_engine(url: str, *, enforce_foreign_keys: bool = True) -> AsyncEngine:
    # Parameters may hold password hashes; keep them out of errors and logs.
    engine = create_async_engine(url, hide_parameters=True)
    if engine.dialect.name == "sqlite":
        configure_sqlite_engine(engine.sync_engine, enforce_foreign_keys=enforce_foreign_keys)
    return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    # No autobegin: a statement outside begin()/read_transaction() raises.
    return async_sessionmaker(engine, expire_on_commit=False, autobegin=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: SessionFactory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def read_transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    async with session.begin():
        await session.connection(execution_options={READ_ONLY_OPTION: True})
        yield session


@asynccontextmanager
async def read_connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as connection:
        reader = await connection.execution_options(**{READ_ONLY_OPTION: True})
        async with reader.begin():
            yield reader
