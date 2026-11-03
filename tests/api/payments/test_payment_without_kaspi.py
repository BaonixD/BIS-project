"""Without ``KASPI_PAYMENT_URL`` cash works end to end and a Kaspi order is refused (503)."""

import httpx
import pytest

from support.auth import register_and_login
from support.dispatch import Dispatcher
from support.drivers import DriverFactory
from support.lifecycle import expect_ok, trip_in
from support.payments import TEST_KASPI_URL, expect_cash_received, read_payment, stored_payment
from support.rides import RIDES_URL, count_rows, request_quote, ride_body, ride_headers
from taxi_service.core.config import Settings
from taxi_service.database.session import SessionFactory
from taxi_service.main import create_app
from taxi_service.modules.payments.models import Payment
from taxi_service.modules.rides.models import IdempotencyRecord, Ride


async def test_cash_ride_is_paid_end_to_end_without_kaspi(
    client: httpx.AsyncClient,
    driver_factory: DriverFactory,
    dispatcher: Dispatcher,
    session_factory: SessionFactory,
) -> None:
    trip = await trip_in("in_progress", client, driver_factory, dispatcher)
    await expect_ok(client, trip, "complete")

    shown = await read_payment(client, trip.ride_id, trip.passenger)
    paid = await expect_cash_received(client, trip.ride_id, trip.driver)

    assert (shown["method"], shown["status"], shown["payment_url"]) == ("cash", "unpaid", None)
    assert (paid["method"], paid["status"], paid["payment_url"]) == ("cash", "paid", None)
    stored = await stored_payment(session_factory, trip.ride_id)
    assert stored is not None
    assert stored.status == "paid"


async def test_kaspi_order_is_unavailable_and_creates_nothing(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    refused = await client.post(
        RIDES_URL,
        json=ride_body(quote["quote_id"], "kaspi_link"),
        headers=ride_headers(passenger, "key-1"),
    )

    assert refused.status_code == 503, refused.text
    assert refused.json()["error"]["code"] == "kaspi_unavailable"
    for model in (Ride, Payment, IdempotencyRecord):
        assert await count_rows(session_factory, model) == 0
    cash = await client.post(
        RIDES_URL, json=ride_body(quote["quote_id"]), headers=ride_headers(passenger, "key-1")
    )
    assert cash.status_code == 201, cash.text
    assert cash.json()["payment_method"] == "cash"


@pytest.mark.parametrize(("value", "enabled"), [("", False), (TEST_KASPI_URL, True)])
def test_create_app_reads_the_kaspi_link_once_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, value: str, enabled: bool
) -> None:
    monkeypatch.setenv("KASPI_PAYMENT_URL", value)

    app = create_app(settings)
    monkeypatch.setenv("KASPI_PAYMENT_URL", "")

    assert app.state.payment_settings.kaspi_enabled is enabled
    assert app.state.payment_settings.kaspi_payment_url == (value or None)
