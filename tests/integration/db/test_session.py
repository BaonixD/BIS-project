import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InvalidRequestError

from taxi_service.database.session import SessionFactory, read_transaction


async def test_session_uses_file_database(
    session_factory: SessionFactory, database_url: str
) -> None:
    async with session_factory() as session, read_transaction(session):
        assert await session.scalar(text("SELECT 1")) == 1
        main_file = await session.scalar(
            text("SELECT file FROM pragma_database_list WHERE name = 'main'")
        )

    assert main_file == make_url(database_url).database


async def test_committed_data_is_visible_to_another_session(
    session_factory: SessionFactory,
) -> None:
    async with session_factory.begin() as writer:
        await writer.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
        await writer.execute(text("INSERT INTO probe (id) VALUES (1)"))

    async with session_factory() as reader, read_transaction(reader):
        assert await reader.scalar(text("SELECT count(*) FROM probe")) == 1


async def test_statement_outside_explicit_transaction_is_refused(
    session_factory: SessionFactory,
) -> None:
    # No autobegin: nothing can hold the SQLite lock until the session closes.
    async with session_factory() as session:
        with pytest.raises(InvalidRequestError, match=r"[Aa]utobegin"):
            await session.execute(text("SELECT 1"))
        assert not session.in_transaction()
