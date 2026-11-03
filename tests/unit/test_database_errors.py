import pytest
from sqlalchemy.exc import IntegrityError

from taxi_service.database.errors import violates_unique

PLATE = {"constraint": "uq_vehicles_plate_number", "table": "vehicles", "column": "plate_number"}


def integrity_error(message: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception(message))


@pytest.mark.parametrize(
    "message",
    [
        "UNIQUE constraint failed: vehicles.plate_number",
        'duplicate key value violates unique constraint "uq_vehicles_plate_number"',
    ],
)
def test_sqlite_and_postgresql_messages_are_recognized(message: str) -> None:
    assert violates_unique(integrity_error(message), **PLATE)


@pytest.mark.parametrize(
    "message",
    [
        "UNIQUE constraint failed: vehicles.driver_id",
        "CHECK constraint failed: ck_vehicles_plate_number_normalized",
        'duplicate key value violates unique constraint "uq_vehicles_driver_id"',
    ],
)
def test_other_constraints_are_not_mapped(message: str) -> None:
    assert not violates_unique(integrity_error(message), **PLATE)
