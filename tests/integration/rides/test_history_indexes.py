"""Ride history pages (T09) are served by an index in the order the API uses.

``ORDER BY created_at DESC, id DESC`` for one passenger or one driver must be a
SEARCH on its history index without a temporary B-tree for sorting.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from taxi_service.modules.rides.models import DRIVER_HISTORY_INDEX, PASSENGER_HISTORY_INDEX


@pytest.mark.parametrize(
    ("column", "index"),
    [("passenger_id", PASSENGER_HISTORY_INDEX), ("driver_id", DRIVER_HISTORY_INDEX)],
)
async def test_history_page_uses_the_index_without_sorting(
    engine: AsyncEngine, column: str, index: str
) -> None:
    query = (
        f"EXPLAIN QUERY PLAN SELECT * FROM rides WHERE {column} = :owner"
        " ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 0"
    )
    async with engine.connect() as connection:
        plan = [row[3] for row in await connection.execute(text(query), {"owner": "0" * 32})]

    assert any(f"USING INDEX {index}" in step for step in plan), plan
    assert not any("TEMP B-TREE" in step for step in plan), plan
