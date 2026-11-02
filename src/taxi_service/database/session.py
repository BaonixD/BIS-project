from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from taxi_service.database.sqlite import configure_sqlite_engine

SessionFactory = async_sessionmaker[AsyncSession]


def create_database_engine(url: str) -> AsyncEngine:
    """Create the application engine; the caller owns it and must ``dispose()`` it.

    SQLite engines get the connection setup described in
    :func:`taxi_service.database.sqlite.configure_sqlite_engine`.
    """
    engine = create_async_engine(url)
    if engine.dialect.name == "sqlite":
        configure_sqlite_engine(engine.sync_engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Sessions keep loaded attributes after commit so responses need no extra SQL."""
    return async_sessionmaker(engine, expire_on_commit=False)
