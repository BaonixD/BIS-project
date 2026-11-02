from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

SessionFactory = async_sessionmaker[AsyncSession]


def create_database_engine(url: str) -> AsyncEngine:
    """Create the application engine; the caller owns it and must ``dispose()`` it."""
    return create_async_engine(url)


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Sessions keep loaded attributes after commit so responses need no extra SQL."""
    return async_sessionmaker(engine, expire_on_commit=False)
