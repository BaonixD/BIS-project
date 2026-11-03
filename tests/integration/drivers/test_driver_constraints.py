"""Database constraints of driver_profiles and vehicles, independent of the Python checks."""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from taxi_service.database.session import SessionFactory, read_transaction

NOW = "2026-11-03 09:00:00.000000"
LOCATION_INDEX = "ix_driver_profiles_longitude_latitude"


async def insert_user(session_factory: SessionFactory, role: str = "driver") -> str:
    user_id = uuid.uuid4().hex
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, username, username_normalized, password_hash, role,"
                " created_at) VALUES (:id, :name, :name, 'hash', :role, :now)"
            ),
            {"id": user_id, "name": f"u{user_id[:8]}", "role": role, "now": NOW},
        )
    return user_id


async def insert_driver(session_factory: SessionFactory, **values: Any) -> str:
    user_id = values.pop("user_id", None) or await insert_user(session_factory)
    row = {
        "user_id": user_id,
        "approval_status": "pending",
        "approved_at": None,
        "approved_by": None,
        "is_online": False,
        "longitude": None,
        "latitude": None,
        "location_updated_at": None,
        "created_at": NOW,
        "updated_at": NOW,
        **values,
    }
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    async with session_factory.begin() as session:
        await session.execute(
            text(f"INSERT INTO driver_profiles ({columns}) VALUES ({params})"), row
        )
    return user_id


async def insert_vehicle(session_factory: SessionFactory, driver_id: str, **values: Any) -> None:
    row = {
        "id": uuid.uuid4().hex,
        "driver_id": driver_id,
        "make": "Toyota",
        "model": "Camry",
        "color": "white",
        "plate_number": "123ABC02",
        "year": 2020,
        "updated_at": NOW,
        **values,
    }
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    async with session_factory.begin() as session:
        await session.execute(text(f"INSERT INTO vehicles ({columns}) VALUES ({params})"), row)


def located(longitude: float, latitude: float) -> dict[str, Any]:
    return {"longitude": longitude, "latitude": latitude, "location_updated_at": NOW}


async def test_valid_rows_are_stored(session_factory: SessionFactory) -> None:
    admin = await insert_user(session_factory, role="admin")
    driver = await insert_driver(
        session_factory,
        approval_status="approved",
        approved_at=NOW,
        approved_by=admin,
        is_online=True,
        **located(180, -90),
    )
    await insert_vehicle(session_factory, driver)


@pytest.mark.parametrize(
    "values",
    [
        located(180.000001, 43.2),
        located(-180.000001, 43.2),
        located(76.9, 90.000001),
        located(76.9, -90.000001),
        {"longitude": 76.9, "latitude": None, "location_updated_at": NOW},
        {"longitude": 76.9, "latitude": 43.2, "location_updated_at": None},
        {"longitude": None, "latitude": None, "location_updated_at": NOW},
    ],
)
async def test_location_must_be_complete_and_in_range(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_driver(session_factory, **values)


@pytest.mark.parametrize(
    "values",
    [
        {"approval_status": "banned"},
        {"approval_status": "approved"},
        {"approval_status": "pending", "approved_at": NOW},
        {"is_online": True},
    ],
)
async def test_approval_and_online_states_are_consistent(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_driver(session_factory, **values)


async def test_approval_needs_the_approving_user(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_driver(session_factory, approval_status="approved", approved_at=NOW)


async def test_driver_profile_belongs_to_an_existing_user(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_driver(session_factory, user_id=uuid.uuid4().hex)


async def test_one_profile_per_user(session_factory: SessionFactory) -> None:
    driver = await insert_driver(session_factory)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_driver(session_factory, user_id=driver)


async def test_one_vehicle_per_driver(session_factory: SessionFactory) -> None:
    driver = await insert_driver(session_factory)
    await insert_vehicle(session_factory, driver, plate_number="111AAA02")

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_vehicle(session_factory, driver, plate_number="222BBB02")


async def test_plate_number_is_unique_across_drivers(session_factory: SessionFactory) -> None:
    await insert_vehicle(session_factory, await insert_driver(session_factory))

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_vehicle(session_factory, await insert_driver(session_factory))


@pytest.mark.parametrize(
    "values",
    [
        {"plate_number": "123abc02"},
        {"plate_number": ""},
        {"year": 1900},
        {"year": 2200},
        {"car_class": "premium"},
    ],
)
async def test_vehicle_values_are_checked(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    driver = await insert_driver(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_vehicle(session_factory, driver, **values)


async def test_vehicle_class_defaults_to_economy(session_factory: SessionFactory) -> None:
    driver = await insert_driver(session_factory)
    await insert_vehicle(session_factory, driver)

    async with session_factory.begin() as session:
        car_class = await session.scalar(text("SELECT car_class FROM vehicles"))

    assert car_class == "economy"


async def test_vehicle_needs_a_driver_profile(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_vehicle(session_factory, uuid.uuid4().hex)


async def test_bounding_box_query_uses_the_location_index(session_factory: SessionFactory) -> None:
    async with session_factory() as session, read_transaction(session):
        columns = await session.scalars(
            text(f"SELECT name FROM pragma_index_info('{LOCATION_INDEX}')")
        )
        plan = await session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT user_id FROM driver_profiles"
                " WHERE longitude BETWEEN 76.8 AND 77.0 AND latitude BETWEEN 43.1 AND 43.3"
            )
        )
        details = " ".join(str(row[-1]) for row in plan)

    assert list(columns) == ["longitude", "latitude"]
    assert LOCATION_INDEX in details
