"""Schema of payments (ADR 0010): only the database accepts or rejects rows.

Rows are inserted with raw SQL through ``support.rows``.
"""

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from support.rows import NOW, insert_driver, insert_payment, insert_ride
from taxi_service.database.session import SessionFactory

UNKNOWN_ID = "0" * 32


async def completed_ride(session_factory: SessionFactory) -> str:
    driver = await insert_driver(session_factory)
    return await insert_ride(session_factory, status="completed", driver_id=driver)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"method": "kaspi_link"},
        {"status": "paid", "paid_at": NOW},
        {"method": "kaspi_link", "status": "paid", "paid_at": NOW},
        {"method": "kaspi_link", "status": "refunded", "paid_at": NOW, "refunded_at": NOW},
    ],
)
async def test_valid_payment_states_are_accepted(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    await insert_payment(session_factory, await completed_ride(session_factory), **values)


async def test_one_payment_per_ride(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)
    await insert_payment(session_factory, ride)

    with pytest.raises(IntegrityError, match="UNIQUE"):
        await insert_payment(session_factory, ride)


async def test_payment_belongs_to_an_existing_ride(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_payment(session_factory, None)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_payment(session_factory, UNKNOWN_ID)


@pytest.mark.parametrize(
    "values",
    [
        {"amount_kzt": 0},
        {"amount_kzt": -1},
        {"currency": "USD"},
        {"method": "card"},
        {"status": "confirmed", "paid_at": NOW},
        {"status": "reported", "paid_at": NOW},
        # unpaid: no times; paid: paid_at only; refunded: both
        {"status": "paid"},
        {"paid_at": NOW},
        {"refunded_at": NOW},
        {"status": "paid", "paid_at": NOW, "refunded_at": NOW},
        {"status": "refunded"},
        {"status": "refunded", "paid_at": NOW},
        {"status": "refunded", "refunded_at": NOW},
    ],
)
async def test_inconsistent_payment_is_rejected(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_payment(session_factory, ride, **values)


@pytest.mark.parametrize(
    "column", ["amount_kzt", "currency", "method", "status", "created_at", "updated_at"]
)
async def test_payment_fields_are_required(session_factory: SessionFactory, column: str) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_payment(session_factory, ride, **{column: None})
