"""Statement parameters never reach exception text, so error logs cannot leak secrets."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import create_database_engine

SECRET = "argon2-hash-that-must-stay-private"


async def test_integrity_error_text_hides_statement_parameters(database_url: str) -> None:
    engine = create_database_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE secrets (value TEXT UNIQUE)"))
            await connection.execute(text("INSERT INTO secrets VALUES (:value)"), {"value": SECRET})
        with pytest.raises(IntegrityError) as caught:
            async with engine.begin() as connection:
                await connection.execute(
                    text("INSERT INTO secrets VALUES (:value)"), {"value": SECRET}
                )
    finally:
        await engine.dispose()

    assert SECRET not in str(caught.value)
