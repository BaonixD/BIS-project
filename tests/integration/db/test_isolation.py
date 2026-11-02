from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from taxi_service.database.migrations import current_revisions, expected_heads
from taxi_service.database.session import SessionFactory, read_transaction


@pytest.mark.parametrize("marker", ["first", "second"])
async def test_committed_rows_do_not_leak_between_tests(
    session_factory: SessionFactory, marker: str
) -> None:
    async with session_factory.begin() as session:
        await session.execute(text("CREATE TABLE IF NOT EXISTS leak_probe (marker TEXT)"))
        assert await session.scalar(text("SELECT count(*) FROM leak_probe")) == 0
        await session.execute(text("INSERT INTO leak_probe VALUES (:marker)"), {"marker": marker})


def test_database_file_belongs_to_this_test(database_url: str, tmp_path: Path) -> None:
    database = make_url(database_url).database
    assert database is not None

    assert Path(database).parent == tmp_path


async def test_database_is_migrated_to_head(session_factory: SessionFactory) -> None:
    async with session_factory() as session, read_transaction(session):
        connection = await session.connection()
        assert await current_revisions(connection) == expected_heads()
