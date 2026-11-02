"""Schema of payments and payment_events (ADR 0004): only the database accepts or rejects rows.

Rows are inserted with raw SQL through ``support.rows``.
"""

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from support.rows import (
    NOW,
    insert_driver,
    insert_payment,
    insert_payment_event,
    insert_ride,
    insert_user,
)
from taxi_service.database.session import SessionFactory

UNKNOWN_ID = "0" * 32


async def completed_ride(session_factory: SessionFactory) -> str:
    driver = await insert_driver(session_factory)
    return await insert_ride(session_factory, status="completed", driver_id=driver)


async def confirmed_values(session_factory: SessionFactory, **values: Any) -> dict[str, Any]:
    confirmer = await insert_user(session_factory, role="admin")
    return {"status": "confirmed", "confirmed_at": NOW, "confirmed_by": confirmer, **values}


async def test_valid_payment_states_are_accepted(session_factory: SessionFactory) -> None:
    await insert_payment(session_factory, await completed_ride(session_factory))
    await insert_payment(
        session_factory,
        await completed_ride(session_factory),
        method="kaspi_link",
        status="reported",
        reported_at=NOW,
    )
    await insert_payment(
        session_factory,
        await completed_ride(session_factory),
        **await confirmed_values(session_factory),
    )
    await insert_payment(
        session_factory,
        await completed_ride(session_factory),
        method="kaspi_link",
        reported_at=NOW,
        **await confirmed_values(session_factory, confirmation_reference="POS 1234"),
    )


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


async def test_confirmer_is_an_existing_user(session_factory: SessionFactory) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_payment(
            session_factory, ride, status="confirmed", confirmed_at=NOW, confirmed_by=UNKNOWN_ID
        )


@pytest.mark.parametrize(
    "values",
    [
        {"amount_kzt": 0},
        {"amount_kzt": -1},
        {"currency": "USD"},
        {"method": "card"},
        {"status": "paid"},
        {"verification": "kaspi_api"},
        # confirmed <=> confirmed_at and confirmed_by
        {"status": "confirmed"},
        {"status": "confirmed", "confirmed_at": NOW},
        {"confirmed_at": NOW},
        # only a Kaspi payment is reported, and reported_at says when
        {"status": "reported", "reported_at": NOW},
        {"method": "kaspi_link", "status": "reported"},
        {"method": "kaspi_link", "reported_at": NOW},
        # a confirmation note belongs to a confirmation
        {"confirmation_reference": "POS 1234"},
    ],
)
async def test_inconsistent_payment_is_rejected(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_payment(session_factory, ride, **values)


@pytest.mark.parametrize(
    "values",
    [
        {"method": "kaspi_link"},  # Kaspi is confirmed only with a reconciliation note
        {"confirmation_reference": ""},
        {"confirmation_reference": "x" * 201},
        {"reported_at": NOW},  # cash has no passenger statement
    ],
)
async def test_inconsistent_confirmation_is_rejected(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    ride = await completed_ride(session_factory)
    confirmed = await confirmed_values(session_factory, **values)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_payment(session_factory, ride, **confirmed)


@pytest.mark.parametrize("column", ["amount_kzt", "currency", "method", "status", "created_at"])
async def test_payment_fields_are_required(session_factory: SessionFactory, column: str) -> None:
    ride = await completed_ride(session_factory)

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_payment(session_factory, ride, **{column: None})


async def payment(session_factory: SessionFactory) -> str:
    return await insert_payment(session_factory, await completed_ride(session_factory))


async def test_valid_payment_events_are_accepted(session_factory: SessionFactory) -> None:
    payment_id = await payment(session_factory)
    actor = await insert_user(session_factory)

    await insert_payment_event(session_factory, payment_id)
    await insert_payment_event(
        session_factory,
        payment_id,
        action="change_method",
        from_status="unpaid",
        from_method="cash",
        to_method="kaspi_link",
        actor_id=actor,
    )
    await insert_payment_event(
        session_factory,
        payment_id,
        action="confirm",
        from_status="reported",
        to_status="confirmed",
        from_method="kaspi_link",
        to_method="kaspi_link",
        actor_id=actor,
        reference="POS 1234",
    )


async def test_event_belongs_to_an_existing_payment(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_payment_event(session_factory, None)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_payment_event(session_factory, UNKNOWN_ID)


async def test_event_actor_is_an_existing_user(session_factory: SessionFactory) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await insert_payment_event(
            session_factory, await payment(session_factory), actor_id=UNKNOWN_ID
        )


CHANGE = {"action": "report", "from_status": "unpaid", "from_method": "kaspi_link"}


@pytest.mark.parametrize(
    "values",
    [
        {"action": "refund"},
        {"to_status": "paid"},
        {"to_method": "card"},
        {**CHANGE, "from_status": "paid"},
        {**CHANGE, "from_method": "card"},
        # only opening has no previous state
        {"from_status": "unpaid"},
        {"from_method": "cash"},
        {"action": "report"},
        {**CHANGE, "from_method": None},
        # a note belongs to a confirmation
        {**CHANGE, "reference": "POS 1234"},
        {**CHANGE, "action": "confirm", "reference": ""},
        {**CHANGE, "action": "confirm", "reference": "x" * 201},
    ],
)
async def test_inconsistent_event_is_rejected(
    session_factory: SessionFactory, values: dict[str, Any]
) -> None:
    payment_id = await payment(session_factory)

    with pytest.raises(IntegrityError, match="CHECK"):
        await insert_payment_event(session_factory, payment_id, **values)


@pytest.mark.parametrize("column", ["action", "to_status", "to_method", "created_at"])
async def test_event_fields_are_required(session_factory: SessionFactory, column: str) -> None:
    payment_id = await payment(session_factory)

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await insert_payment_event(session_factory, payment_id, **{column: None})
