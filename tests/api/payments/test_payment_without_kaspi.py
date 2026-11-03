"""Without ``KASPI_PAYMENT_URL`` cash works end to end and Kaspi is unavailable (503)."""

import httpx
import pytest

from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.lifecycle import expect_ok, trip_in
from support.payments import (
    TEST_KASPI_URL,
    actions_of,
    expect_paid_ok,
    pay,
    read_payment,
    stored_payment,
)
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory
from taxi_service.main import create_app


async def test_cash_ride_is_paid_end_to_end_without_kaspi(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    await expect_ok(client, trip, "complete")

    shown = await read_payment(client, trip.ride_id, trip.passenger)
    confirmed = await expect_paid_ok(client, trip.ride_id, "confirm", trip.driver)

    assert (shown["method"], shown["status"]) == ("cash", "unpaid")
    assert (shown["kaspi_available"], shown["payment_url"]) == (False, None)
    assert (confirmed["status"], confirmed["verification"]) == ("confirmed", "manual")
    assert await actions_of(session_factory, trip.ride_id) == ["open", "confirm"]


async def test_switching_to_kaspi_is_unavailable(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("completed", client, driver_factory, dispatcher)

    response = await pay(
        client, trip.ride_id, "method", trip.passenger, json={"method": "kaspi_link"}
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "kaspi_unavailable"
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert (stored.method, stored.status) == ("cash", "unpaid")
    assert await actions_of(session_factory, trip.ride_id) == ["open"]


@pytest.mark.parametrize(("value", "enabled"), [("", False), (TEST_KASPI_URL, True)])
def test_create_app_reads_the_kaspi_link_once_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, value: str, enabled: bool
) -> None:
    monkeypatch.setenv("KASPI_PAYMENT_URL", value)

    app = create_app(settings)
    monkeypatch.setenv("KASPI_PAYMENT_URL", "")

    assert app.state.payment_settings.kaspi_enabled is enabled
    assert app.state.payment_settings.kaspi_payment_url == (value or None)
