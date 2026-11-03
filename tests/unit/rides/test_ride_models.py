"""The partial unique indexes keep their WHERE clause on PostgreSQL too (ADR 0001)."""

import pytest
from sqlalchemy import Table
from sqlalchemy.engine import URL, Dialect
from sqlalchemy.schema import CreateIndex

from taxi_service.modules.rides.models import (
    ACTIVE_DRIVER_RIDE_INDEX,
    ACTIVE_PASSENGER_RIDE_INDEX,
    Ride,
)

EXPECTED_WHERE = {
    ACTIVE_PASSENGER_RIDE_INDEX: "status IN ('arrived', 'assigned', 'in_progress', 'searching')",
    ACTIVE_DRIVER_RIDE_INDEX: "status IN ('arrived', 'assigned', 'in_progress')",
}
DIALECTS = [URL.create(name).get_dialect()() for name in ("sqlite", "postgresql")]


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("name", sorted(EXPECTED_WHERE))
def test_active_ride_index_is_partial_and_unique(dialect: Dialect, name: str) -> None:
    table = Ride.__table__
    assert isinstance(table, Table)
    [index] = [index for index in table.indexes if index.name == name]

    ddl = str(CreateIndex(index).compile(dialect=dialect))

    assert ddl.startswith("CREATE UNIQUE INDEX")
    assert ddl.endswith(f"WHERE {EXPECTED_WHERE[name]}")
