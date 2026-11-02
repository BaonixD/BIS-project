"""Payment of a completed ride through the API with a controlled Kaspi link (ADR 0004).

Kaspi is on with ``TEST_KASPI_URL``; no request leaves the test process and no
real payment is made. Passenger ``pat``, driver ``dana``, admin ``admin``.
"""

import asyncio
import uuid
from typing import Any

import httpx
import pytest

from support.auth import register_and_login
from support.clock import ManualClock
from support.dispatch import Dispatcher
from support.drivers import DriverFactory, login_as
from support.lifecycle import Trip, trip_in
from support.payments import (
    ADMIN,
    REFERENCE,
    TEST_KASPI_URL,
    AuditEvent,
    actions_of,
    expect_paid_ok,
    kaspi_on,
    pay,
    payment_events,
    payment_url,
    read_payment,
    stored_payment,
)
from support.rows import insert_driver, insert_payment, insert_ride
from taxi_service.database.session import SessionFactory
from taxi_service.modules.payments.config import PaymentSettings

KASPI = {"method": "kaspi_link"}
CASH = {"method": "cash"}


@pytest.fixture
def payment_settings() -> PaymentSettings:
    return kaspi_on()


@pytest.fixture
async def completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> Trip:
    """A completed trip of ``pat`` with ``dana``; the admin account exists."""
    trip = await trip_in("completed", client, driver_factory, dispatcher)
    await driver_factory.admin_id()
    return trip


async def stranger(client: httpx.AsyncClient, driver_factory: DriverFactory, role: str) -> str:
    """Another passenger or driver who has nothing to do with the trip."""
    if role == "driver":
        await driver_factory.driver("other_driver")
        return "other_driver"
    await register_and_login(client, "other_passenger")
    return "other_passenger"


def expect_error(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert body["error"]["code"] == code
    return body


# Instructions


async def test_passenger_gets_cash_instructions_after_completion(
    client: httpx.AsyncClient, completed: Trip
) -> None:
    body = await read_payment(client, completed.ride_id, completed.passenger)

    assert body == {
        "ride_id": str(completed.ride_id),
        "amount_kzt": 2200,
        "currency": "KZT",
        "method": "cash",
        "status": "unpaid",
        "verification": "manual",
        "kaspi_available": True,
        "payment_url": None,
        "amount_entered_by_buyer": False,
        "notice": body["notice"],
        "reported_at": None,
        "confirmed_at": None,
        "confirmed_by": None,
        "confirmation_reference": None,
    }
    assert "cash" in body["notice"]


@pytest.mark.parametrize("username", ["dana", ADMIN])
async def test_driver_and_admin_see_the_payment(
    client: httpx.AsyncClient, completed: Trip, username: str
) -> None:
    body = await read_payment(client, completed.ride_id, username)

    assert (body["status"], body["verification"]) == ("unpaid", "manual")


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_does_not_see_the_payment(
    client: httpx.AsyncClient, driver_factory: DriverFactory, completed: Trip, role: str
) -> None:
    username = await stranger(client, driver_factory, role)
    await login_as(client, username)

    expect_error(await client.get(payment_url(completed.ride_id)), 404, "ride_not_found")


async def test_unknown_ride_has_no_payment(client: httpx.AsyncClient, completed: Trip) -> None:
    await login_as(client, completed.passenger)

    expect_error(await client.get(payment_url(uuid.uuid4())), 404, "ride_not_found")


async def test_payment_needs_a_session(client: httpx.AsyncClient, completed: Trip) -> None:
    client.cookies.clear()

    expect_error(await client.get(payment_url(completed.ride_id)), 401, "not_authenticated")


@pytest.mark.parametrize("status", ["assigned", "in_progress", "cancelled"])
async def test_no_payment_before_the_ride_is_completed(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher, status: str
) -> None:
    trip = await trip_in(status, client, driver_factory, dispatcher)
    await login_as(client, trip.passenger)

    expect_error(await client.get(payment_url(trip.ride_id)), 409, "ride_not_completed")


# Cash


async def test_assigned_driver_confirms_cash(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    body = await expect_paid_ok(client, completed.ride_id, "confirm", completed.driver)

    assert body["status"] == "confirmed"
    assert body["method"] == "cash"
    assert body["verification"] == "manual"
    assert body["changed"] is True
    assert body["confirmed_by"] == str(completed.driver_id)
    assert body["confirmed_at"] is not None
    assert body["amount_kzt"] == 2200
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.status, stored.confirmed_by, stored.confirmed_at) == (
        "confirmed",
        completed.driver_id,
        clock.now(),
    )
    assert await payment_events(session_factory, completed.ride_id) == [
        AuditEvent("open", None, "unpaid", None, "cash", None, None),
        AuditEvent("confirm", "unpaid", "confirmed", "cash", "cash", completed.driver_id, None),
    ]


async def test_admin_confirms_cash_with_an_optional_note(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    body = await expect_paid_ok(
        client, completed.ride_id, "confirm", ADMIN, json={"reference": "  cash at the office "}
    )

    admin_id = await driver_factory.admin_id()
    assert (body["status"], body["confirmed_by"]) == ("confirmed", str(admin_id))
    assert body["confirmation_reference"] == "cash at the office"
    [*_, event] = await payment_events(session_factory, completed.ride_id)
    assert (event.action, event.actor_id, event.reference) == (
        "confirm",
        admin_id,
        "cash at the office",
    )


async def test_passenger_cannot_confirm(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    response = await pay(client, completed.ride_id, "confirm", completed.passenger)

    body = expect_error(response, 403, "payment_action_forbidden")
    assert body["error"]["details"] == {"action": "confirm"}
    assert await actions_of(session_factory, completed.ride_id) == ["open"]


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_confirm(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    session_factory: SessionFactory,
    role: str,
) -> None:
    username = await stranger(client, driver_factory, role)

    response = await pay(client, completed.ride_id, "confirm", username)

    expect_error(response, 404, "ride_not_found")
    assert await actions_of(session_factory, completed.ride_id) == ["open"]


async def test_driver_cannot_confirm_before_completion(
    client: httpx.AsyncClient, driver_factory: DriverFactory, dispatcher: Dispatcher
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)

    response = await pay(client, trip.ride_id, "confirm", trip.driver)

    expect_error(response, 409, "ride_not_completed")


async def test_repeated_confirm_is_already_confirmed_without_a_second_event(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    first = await expect_paid_ok(client, completed.ride_id, "confirm", completed.driver)

    again = await expect_paid_ok(client, completed.ride_id, "confirm", ADMIN)

    assert again["changed"] is False
    assert again["status"] == "confirmed"
    assert again["confirmed_by"] == first["confirmed_by"]
    assert again["confirmed_at"] == first["confirmed_at"]
    assert await actions_of(session_factory, completed.ride_id) == ["open", "confirm"]


async def test_concurrent_confirms_record_one_confirmation(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    driver = await login_as(client, completed.driver)
    admin = await login_as(other_client, ADMIN)
    url = payment_url(completed.ride_id, "confirm")

    responses = await asyncio.gather(
        client.post(url, headers=driver.csrf_headers),
        other_client.post(url, headers=admin.csrf_headers),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["changed"] for response in responses) == [False, True]
    assert await actions_of(session_factory, completed.ride_id) == ["open", "confirm"]


async def test_cash_confirmation_against_switch_to_kaspi(
    client: httpx.AsyncClient,
    other_client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    driver = await login_as(client, completed.driver)
    passenger = await login_as(other_client, completed.passenger)

    confirmed, switched = await asyncio.gather(
        client.post(payment_url(completed.ride_id, "confirm"), headers=driver.csrf_headers),
        other_client.put(
            payment_url(completed.ride_id, "method"), json=KASPI, headers=passenger.csrf_headers
        ),
    )

    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    actions = await actions_of(session_factory, completed.ride_id)
    if confirmed.status_code == 200:  # the confirmation won: the payment stays cash
        expect_error(switched, 409, "invalid_payment_transition")
        assert (stored.method, stored.status, stored.confirmed_by) == (
            "cash",
            "confirmed",
            completed.driver_id,
        )
        assert actions == ["open", "confirm"]
    else:  # the switch won: a driver never confirms Kaspi
        expect_error(confirmed, 403, "payment_action_forbidden")
        assert switched.status_code == 200, switched.text
        assert (stored.method, stored.status, stored.confirmed_by) == ("kaspi_link", "unpaid", None)
        assert actions == ["open", "change_method"]


async def test_confirming_one_payment_leaves_other_rides_alone(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    other_ride = await insert_ride(
        session_factory, status="completed", driver_id=await insert_driver(session_factory)
    )
    await insert_payment(session_factory, other_ride)

    await expect_paid_ok(client, completed.ride_id, "confirm", completed.driver)

    other = await stored_payment(session_factory, uuid.UUID(other_ride))
    assert other is not None
    assert (other.status, other.confirmed_by) == ("unpaid", None)


# Kaspi


async def test_passenger_switches_to_kaspi_and_gets_the_configured_link(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    body = await expect_paid_ok(
        client, completed.ride_id, "method", completed.passenger, json=KASPI
    )

    assert (body["method"], body["status"], body["changed"]) == ("kaspi_link", "unpaid", True)
    assert body["payment_url"] == TEST_KASPI_URL
    assert body["amount_entered_by_buyer"] is True
    assert body["amount_kzt"] == 2200
    assert body["verification"] == "manual"
    assert await payment_events(session_factory, completed.ride_id) == [
        AuditEvent("open", None, "unpaid", None, "cash", None, None),
        AuditEvent(
            "change_method", "unpaid", "unpaid", "cash", "kaspi_link", completed.passenger_id, None
        ),
    ]


async def test_choosing_the_current_method_again_changes_nothing(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    body = await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=CASH)

    assert (body["method"], body["changed"]) == ("cash", False)
    assert await actions_of(session_factory, completed.ride_id) == ["open"]


async def test_kaspi_report_is_only_a_statement(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    clock: ManualClock,
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)

    body = await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    assert (body["status"], body["changed"], body["verification"]) == ("reported", True, "manual")
    assert body["confirmed_at"] is None
    assert body["confirmed_by"] is None
    assert body["payment_url"] == TEST_KASPI_URL
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.status, stored.reported_at, stored.confirmed_at) == (
        "reported",
        clock.now(),
        None,
    )
    [*_, event] = await payment_events(session_factory, completed.ride_id)
    assert event == AuditEvent(
        "report", "unpaid", "reported", "kaspi_link", "kaspi_link", completed.passenger_id, None
    )
    shown = await read_payment(client, completed.ride_id, completed.passenger)
    assert shown["status"] == "reported"


async def test_repeated_report_changes_nothing(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    again = await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    assert (again["status"], again["changed"]) == ("reported", False)
    assert await actions_of(session_factory, completed.ride_id) == [
        "open",
        "change_method",
        "report",
    ]


@pytest.mark.parametrize("username", ["dana", "pat"])
async def test_only_admin_confirms_kaspi(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory, username: str
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    response = await pay(
        client, completed.ride_id, "confirm", username, json={"reference": REFERENCE}
    )

    expect_error(response, 403, "payment_action_forbidden")
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.status == "reported"


@pytest.mark.parametrize("payload", [None, {}, {"reference": None}, {"reference": "   "}])
async def test_kaspi_confirmation_needs_a_reference(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    payload: dict[str, Any] | None,
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    response = await pay(client, completed.ride_id, "confirm", ADMIN, json=payload)

    expect_error(response, 422, "confirmation_reference_required")
    assert await actions_of(session_factory, completed.ride_id) == [
        "open",
        "change_method",
        "report",
    ]


@pytest.mark.parametrize("reference", ["x" * 201, "line\nbreak", "bidi‮mark"])
async def test_invalid_reference_is_rejected(
    client: httpx.AsyncClient, completed: Trip, reference: str
) -> None:
    response = await pay(client, completed.ride_id, "confirm", ADMIN, json={"reference": reference})

    body = expect_error(response, 422, "invalid_confirmation_reference")
    assert body["error"]["details"] == {"max_length": 200}


async def test_admin_confirms_reported_kaspi_with_a_reference(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    session_factory: SessionFactory,
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    body = await expect_paid_ok(
        client, completed.ride_id, "confirm", ADMIN, json={"reference": REFERENCE}
    )

    admin_id = await driver_factory.admin_id()
    assert (body["status"], body["method"], body["changed"]) == ("confirmed", "kaspi_link", True)
    assert body["verification"] == "manual"
    assert body["payment_url"] is None
    assert body["confirmation_reference"] == REFERENCE
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.confirmed_by, stored.confirmation_reference) == (admin_id, REFERENCE)
    assert stored.reported_at is not None
    [*_, event] = await payment_events(session_factory, completed.ride_id)
    assert event == AuditEvent(
        "confirm", "reported", "confirmed", "kaspi_link", "kaspi_link", admin_id, REFERENCE
    )
    shown = await read_payment(client, completed.ride_id, completed.passenger)
    assert (shown["status"], shown["payment_url"]) == ("confirmed", None)
    assert shown["confirmation_reference"] is None  # the reconciliation note is for admins


async def test_admin_confirms_unreported_kaspi_after_reconciliation(
    client: httpx.AsyncClient, completed: Trip
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)

    body = await expect_paid_ok(
        client, completed.ride_id, "confirm", ADMIN, json={"reference": REFERENCE}
    )

    assert (body["status"], body["changed"]) == ("confirmed", True)


async def test_repeated_kaspi_confirmation_keeps_the_first_one(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    first = await expect_paid_ok(
        client, completed.ride_id, "confirm", ADMIN, json={"reference": REFERENCE}
    )

    without_note = await pay(client, completed.ride_id, "confirm", ADMIN)
    again = await expect_paid_ok(
        client, completed.ride_id, "confirm", ADMIN, json={"reference": "another note"}
    )

    expect_error(without_note, 422, "confirmation_reference_required")
    assert again["changed"] is False
    assert (again["confirmed_at"], again["confirmation_reference"]) == (
        first["confirmed_at"],
        REFERENCE,
    )
    assert await actions_of(session_factory, completed.ride_id) == [
        "open",
        "change_method",
        "confirm",
    ]


async def test_back_to_cash_drops_the_kaspi_statement(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=KASPI)
    await expect_paid_ok(client, completed.ride_id, "report", completed.passenger)

    body = await expect_paid_ok(client, completed.ride_id, "method", completed.passenger, json=CASH)

    assert (body["method"], body["status"], body["payment_url"]) == ("cash", "unpaid", None)
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert stored.reported_at is None
    confirmed = await expect_paid_ok(client, completed.ride_id, "confirm", completed.driver)
    assert confirmed["status"] == "confirmed"


async def test_method_cannot_change_after_confirmation(
    client: httpx.AsyncClient, completed: Trip, session_factory: SessionFactory
) -> None:
    await expect_paid_ok(client, completed.ride_id, "confirm", completed.driver)

    response = await pay(client, completed.ride_id, "method", completed.passenger, json=KASPI)

    body = expect_error(response, 409, "invalid_payment_transition")
    assert body["error"]["details"] == {
        "action": "change_method",
        "method": "cash",
        "status": "confirmed",
    }
    assert await actions_of(session_factory, completed.ride_id) == ["open", "confirm"]


async def test_cash_has_no_report(client: httpx.AsyncClient, completed: Trip) -> None:
    response = await pay(client, completed.ride_id, "report", completed.passenger)

    expect_error(response, 409, "invalid_payment_transition")


@pytest.mark.parametrize(("action", "payload"), [("method", KASPI), ("report", None)])
@pytest.mark.parametrize("username", ["dana", ADMIN])
async def test_only_the_passenger_chooses_and_reports(
    client: httpx.AsyncClient,
    completed: Trip,
    action: str,
    payload: dict[str, Any] | None,
    username: str,
) -> None:
    response = await pay(client, completed.ride_id, action, username, json=payload)

    expect_error(response, 403, "payment_action_forbidden")


@pytest.mark.parametrize(("action", "payload"), [("method", KASPI), ("report", None)])
@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_stranger_cannot_choose_or_report(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    completed: Trip,
    action: str,
    payload: dict[str, Any] | None,
    role: str,
) -> None:
    username = await stranger(client, driver_factory, role)

    response = await pay(client, completed.ride_id, action, username, json=payload)

    expect_error(response, 404, "ride_not_found")


# Forged bodies and CSRF


@pytest.mark.parametrize(
    ("action", "username", "payload"),
    [
        ("method", "pat", {"method": "kaspi_link", "payment_url": "https://pay.kaspi.kz/pay/evil"}),
        ("method", "pat", {"method": "kaspi_link", "amount_kzt": 1}),
        ("method", "pat", {"method": "card"}),
        ("method", "pat", {}),
        ("report", "pat", {"amount_kzt": 1}),
        ("report", "pat", {"status": "confirmed"}),
        ("confirm", ADMIN, {"reference": REFERENCE, "amount_kzt": 1}),
        ("confirm", ADMIN, {"reference": REFERENCE, "payment_url": "https://evil.example"}),
        ("confirm", "dana", {"verification": "kaspi_api"}),
    ],
)
async def test_forged_fields_are_rejected(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    action: str,
    username: str,
    payload: dict[str, Any],
) -> None:
    response = await pay(client, completed.ride_id, action, username, json=payload)

    expect_error(response, 422, "validation_error")
    stored = await stored_payment(session_factory, completed.ride_id)
    assert stored is not None
    assert (stored.amount_kzt, stored.method, stored.status) == (2200, "cash", "unpaid")
    assert await actions_of(session_factory, completed.ride_id) == ["open"]


@pytest.mark.parametrize(
    ("method", "action", "payload"),
    [("put", "method", KASPI), ("post", "report", None), ("post", "confirm", None)],
)
async def test_commands_need_the_csrf_token(
    client: httpx.AsyncClient,
    completed: Trip,
    session_factory: SessionFactory,
    method: str,
    action: str,
    payload: dict[str, Any] | None,
) -> None:
    await login_as(client, completed.driver if action == "confirm" else completed.passenger)

    response = await client.request(
        method.upper(), payment_url(completed.ride_id, action), json=payload
    )

    expect_error(response, 403, "csrf_failed")
    assert await actions_of(session_factory, completed.ride_id) == ["open"]
