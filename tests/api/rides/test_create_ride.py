"""POST /api/v1/rides: a ride from the passenger's own quote, safe to repeat and to race."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update

from support.auth import CSRF_HEADER, LoggedInUser, register_and_login
from support.clock import ManualClock
from support.drivers import create_admin, login_as
from support.payments import kaspi_on
from support.rides import (
    RIDES_URL,
    count_rows,
    order_ride,
    request_quote,
    ride_body,
    ride_headers,
)
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.rides import service
from taxi_service.modules.rides.idempotency import IDEMPOTENCY_HEADER
from taxi_service.modules.rides.models import IdempotencyRecord, Ride
from taxi_service.modules.rides.pricing import Fare
from taxi_service.modules.rides.states import RideStatus

REPLAY_HEADER = "Idempotent-Replayed"
SNAPSHOT_FIELDS = ("pickup", "dropoff", "route", "amount_kzt", "currency", "tariff_version")
# Stage times and cancel reason (T07B); empty on a new ride.
LIFECYCLE_FIELDS = (
    "assigned_at",
    "arrived_at",
    "started_at",
    "completed_at",
    "cancelled_at",
    "cancel_reason",
)


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def post_ride(
    client: httpx.AsyncClient,
    user: LoggedInUser,
    quote_id: str,
    key: str | None = None,
    payment_method: str | None = None,
) -> httpx.Response:
    return await client.post(
        RIDES_URL, json=ride_body(quote_id, payment_method), headers=ride_headers(user, key)
    )


async def stored_rides(session_factory: SessionFactory) -> list[Ride]:
    async with session_factory() as session, read_transaction(session):
        return list(await session.scalars(select(Ride)))


# Creation


@pytest.mark.usefixtures("available_driver")
async def test_passenger_creates_a_searching_ride_from_the_quote(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await post_ride(client, passenger, quote["quote_id"])

    assert response.status_code == 201, response.text
    assert REPLAY_HEADER not in response.headers
    ride = response.json()
    assert set(ride) == {
        "id",
        "status",
        "passenger_id",
        "driver_id",
        "quote_id",
        *SNAPSHOT_FIELDS,
        "created_at",
        "updated_at",
        *LIFECYCLE_FIELDS,
        "payment_method",
        "payment_status",
    }
    assert {name: ride[name] for name in LIFECYCLE_FIELDS} == dict.fromkeys(LIFECYCLE_FIELDS)
    assert ride["status"] == "searching"
    assert ride["driver_id"] is None
    assert ride["passenger_id"] == str(passenger.id)
    assert ride["quote_id"] == quote["quote_id"]
    assert {name: ride[name] for name in SNAPSHOT_FIELDS} == {
        name: quote[name] for name in SNAPSHOT_FIELDS
    }
    assert (ride["amount_kzt"], ride["currency"], ride["tariff_version"]) == (2200, "KZT", "edu-v1")
    assert datetime.fromisoformat(ride["created_at"]) == clock.now()
    assert datetime.fromisoformat(ride["updated_at"]) == clock.now()
    assert (ride["payment_method"], ride["payment_status"]) == ("cash", "unpaid")


@pytest.mark.usefixtures("available_driver")
async def test_ride_and_its_idempotency_record_are_stored(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")

    body = await order_ride(client, passenger, key="key-1")

    [ride] = await stored_rides(session_factory)
    assert str(ride.id) == body["id"]
    assert (ride.status, ride.driver_id, ride.passenger_id) == (
        RideStatus.SEARCHING,
        None,
        passenger.id,
    )
    assert (ride.amount_kzt, ride.tariff_version, ride.distance_m) == (2200, "edu-v1", 10_000)
    async with session_factory() as session, read_transaction(session):
        [record] = list(await session.scalars(select(IdempotencyRecord)))
    assert (record.user_id, record.operation, record.key) == (passenger.id, "create_ride", "key-1")
    assert record.resource_id == ride.id
    assert len(record.request_fingerprint) == 64


@pytest.mark.parametrize(
    "extra",
    [
        {"amount_kzt": 1},
        {"currency": "USD"},
        {"tariff_version": "free"},
        {"status": "assigned"},
        {"driver_id": str(uuid.uuid4())},
    ],
)
async def test_price_or_state_in_the_body_is_rejected(
    client: httpx.AsyncClient, session_factory: SessionFactory, extra: dict[str, Any]
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await client.post(
        RIDES_URL, json={"quote_id": quote["quote_id"], **extra}, headers=ride_headers(passenger)
    )

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert await count_rows(session_factory, Ride) == 0


@pytest.mark.parametrize("payment_method", ["card", "", None, "CASH"])
async def test_unknown_payment_method_is_rejected(
    client: httpx.AsyncClient, session_factory: SessionFactory, payment_method: Any
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await client.post(
        RIDES_URL,
        json={"quote_id": quote["quote_id"], "payment_method": payment_method},
        headers=ride_headers(passenger),
    )

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert await count_rows(session_factory, Ride) == 0


@pytest.mark.parametrize("body", [{}, {"quote_id": "not-a-uuid"}, {"quote_id": None}, []])
async def test_quote_id_is_required(client: httpx.AsyncClient, body: Any) -> None:
    passenger = await register_and_login(client, "pat")

    response = await client.post(RIDES_URL, json=body, headers=ride_headers(passenger))

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


# Idempotency-Key header


async def test_idempotency_key_is_required(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await client.post(
        RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=passenger.csrf_headers
    )

    assert response.status_code == 422
    assert error_code(response) == "idempotency_key_required"
    assert await count_rows(session_factory, Ride) == 0


@pytest.mark.parametrize("key", [b"", b"x" * 129, b"a b", "ключ".encode()])
async def test_malformed_idempotency_key_is_rejected(
    client: httpx.AsyncClient, session_factory: SessionFactory, key: bytes
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    headers = [(CSRF_HEADER.encode(), passenger.csrf_token.encode()), (b"Idempotency-Key", key)]

    response = await client.post(RIDES_URL, json={"quote_id": quote["quote_id"]}, headers=headers)

    assert response.status_code == 422
    assert error_code(response) == "idempotency_key_invalid"
    assert await count_rows(session_factory, Ride) == 0


@pytest.mark.parametrize("key", ["k", "x" * 128, "order#1:!~"])
async def test_idempotency_key_limits_are_inclusive(client: httpx.AsyncClient, key: str) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await post_ride(client, passenger, quote["quote_id"], key)

    assert response.status_code == 201


# Quote checks


async def test_unknown_quote_is_not_found(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")

    response = await post_ride(client, passenger, str(uuid.uuid4()))

    assert response.status_code == 404
    assert error_code(response) == "quote_not_found"


async def test_another_passengers_quote_is_not_found(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    owner = await register_and_login(client, "owner")
    quote = await request_quote(client, owner)
    stranger = await register_and_login(client, "stranger")

    response = await post_ride(client, stranger, quote["quote_id"])

    assert response.status_code == 404
    assert error_code(response) == "quote_not_found"
    assert response.json()["error"]["details"] == {}
    assert await count_rows(session_factory, Ride) == 0


async def test_quote_expires_after_five_minutes(
    client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    clock.advance(timedelta(minutes=5))

    response = await post_ride(client, passenger, quote["quote_id"])

    assert response.status_code == 409
    assert error_code(response) == "quote_expired"
    assert await count_rows(session_factory, Ride) == 0


async def test_quote_is_valid_just_before_expiry(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    clock.advance(timedelta(minutes=5) - timedelta(microseconds=1))

    response = await post_ride(client, passenger, quote["quote_id"])

    assert response.status_code == 201


async def test_used_quote_cannot_start_another_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    assert (await post_ride(client, passenger, quote["quote_id"], "first")).status_code == 201

    response = await post_ride(client, passenger, quote["quote_id"], "second")

    assert response.status_code == 409
    assert error_code(response) == "quote_already_used"
    assert await count_rows(session_factory, Ride) == 1


@pytest.mark.usefixtures("available_driver")
async def test_one_active_ride_per_passenger(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    await order_ride(client, passenger)
    second_quote = await request_quote(client, passenger)

    response = await post_ride(client, passenger, second_quote["quote_id"])

    assert response.status_code == 409
    assert error_code(response) == "active_ride_exists"
    assert await count_rows(session_factory, Ride) == 1


# Tariff snapshot


async def test_tariff_change_does_not_reprice_a_stored_quote_or_ride(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    passenger = await register_and_login(client, "pat")
    old_quote = await request_quote(client, passenger)
    monkeypatch.setattr(
        service, "calculate_fare", lambda **_: Fare(amount_kzt=9999, tariff_version="edu-v2")
    )

    ride = (await post_ride(client, passenger, old_quote["quote_id"])).json()
    new_quote = await request_quote(client, passenger)

    assert (ride["amount_kzt"], ride["tariff_version"]) == (2200, "edu-v1")
    assert (new_quote["amount_kzt"], new_quote["tariff_version"]) == (9999, "edu-v2")


# Repeats with the same Idempotency-Key


async def test_repeat_with_the_same_key_and_body_returns_the_same_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    first = await post_ride(client, passenger, quote["quote_id"], "key-1")

    repeat = await post_ride(client, passenger, quote["quote_id"], "key-1")

    assert repeat.status_code == 201
    assert repeat.headers[REPLAY_HEADER] == "true"
    assert repeat.json() == first.json()
    assert await count_rows(session_factory, Ride) == 1
    assert await count_rows(session_factory, IdempotencyRecord) == 1


async def test_repeat_is_answered_even_after_the_quote_expired(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    first = await post_ride(client, passenger, quote["quote_id"], "key-1")
    clock.advance(timedelta(hours=1))

    repeat = await post_ride(client, passenger, quote["quote_id"], "key-1")

    assert repeat.status_code == 201
    assert repeat.json()["id"] == first.json()["id"]


async def test_same_key_with_another_quote_is_a_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    await order_ride(client, passenger, key="key-1")
    other_quote = await request_quote(client, passenger)

    response = await post_ride(client, passenger, other_quote["quote_id"], "key-1")

    assert response.status_code == 409
    assert error_code(response) == "idempotency_key_reused"
    assert await count_rows(session_factory, Ride) == 1


async def test_omitted_method_repeats_as_explicit_cash(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    first = await post_ride(client, passenger, quote["quote_id"], "key-1")

    repeat = await post_ride(client, passenger, quote["quote_id"], "key-1", "cash")

    assert repeat.status_code == 201
    assert repeat.headers[REPLAY_HEADER] == "true"
    assert repeat.json()["id"] == first.json()["id"]


async def test_same_key_with_another_payment_method_is_a_conflict(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    app.state.payment_settings = kaspi_on()
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    await post_ride(client, passenger, quote["quote_id"], "key-1")

    response = await post_ride(client, passenger, quote["quote_id"], "key-1", "kaspi_link")

    assert response.status_code == 409
    assert error_code(response) == "idempotency_key_reused"
    assert await count_rows(session_factory, Ride) == 1


async def test_keys_are_scoped_per_user(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    first = await register_and_login(client, "pat")
    first_ride = await order_ride(client, first, key="shared-key")
    second = await register_and_login(client, "sam")

    second_ride = await order_ride(client, second, key="shared-key")

    assert second_ride["id"] != first_ride["id"]
    assert second_ride["passenger_id"] == str(second.id)
    assert await count_rows(session_factory, Ride) == 2


async def test_failed_attempt_does_not_reserve_the_key(
    client: httpx.AsyncClient, clock: ManualClock
) -> None:
    passenger = await register_and_login(client, "pat")
    stale = await request_quote(client, passenger)
    clock.advance(timedelta(minutes=5))
    assert (await post_ride(client, passenger, stale["quote_id"], "key-1")).status_code == 409
    fresh = await request_quote(client, passenger)

    response = await post_ride(client, passenger, fresh["quote_id"], "key-1")

    assert response.status_code == 201


# Who may create


@pytest.mark.parametrize("role", ["driver", "admin"])
async def test_only_a_passenger_creates_a_ride(
    app: FastAPI,
    client: httpx.AsyncClient,
    session_factory: SessionFactory,
    clock: ManualClock,
    role: str,
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    if role == "admin":
        await create_admin(app, session_factory, clock)
        user = await login_as(client, "admin")
    else:
        user = await register_and_login(client, "dana", role="driver")

    response = await post_ride(client, user, quote["quote_id"])

    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert await count_rows(session_factory, Ride) == 0


async def test_ride_creation_needs_the_csrf_token(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    response = await client.post(
        RIDES_URL,
        json={"quote_id": quote["quote_id"]},
        headers={CSRF_HEADER: "wrong", IDEMPOTENCY_HEADER: "key-1"},
    )

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


# Concurrent requests: two at a time, each on its own session and connection


@pytest.mark.usefixtures("available_driver")
async def test_two_simultaneous_orders_create_one_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    first, second = [await request_quote(client, passenger) for _ in range(2)]

    responses = await asyncio.gather(
        post_ride(client, passenger, first["quote_id"], "key-a"),
        post_ride(client, passenger, second["quote_id"], "key-b"),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    [conflict] = [response for response in responses if response.status_code == 409]
    assert error_code(conflict) == "active_ride_exists"
    assert await count_rows(session_factory, Ride) == 1


async def test_simultaneous_repeats_of_one_key_create_one_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)

    responses = await asyncio.gather(
        post_ride(client, passenger, quote["quote_id"], "key-1"),
        post_ride(client, passenger, quote["quote_id"], "key-1"),
    )

    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert await count_rows(session_factory, Ride) == 1


# The database decides when the Python checks ran on stale data


@pytest.fixture
def stale_checks(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """From now on, the first call of each pre-check misses what another request just
    committed, as under a weaker isolation level; only constraints can refuse the insert.
    """

    def miss_once(name: str, empty: object) -> None:
        original: Callable[..., Awaitable[Any]] = getattr(service, name)
        missed: list[bool] = []

        async def check(*args: Any) -> Any:
            if not missed:
                missed.append(True)
                return empty
            return await original(*args)

        monkeypatch.setattr(service, name, check)

    def activate() -> None:
        miss_once("_get_idempotency_record", None)
        miss_once("_quote_is_used", False)
        miss_once("_has_active_ride", False)

    return activate


async def test_constraint_race_on_the_same_key_returns_the_first_ride(
    client: httpx.AsyncClient, session_factory: SessionFactory, stale_checks: Callable[[], None]
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    first = await post_ride(client, passenger, quote["quote_id"], "key-1")
    stale_checks()

    repeat = await post_ride(client, passenger, quote["quote_id"], "key-1")

    assert repeat.status_code == 201
    assert repeat.headers[REPLAY_HEADER] == "true"
    assert repeat.json()["id"] == first.json()["id"]
    assert await count_rows(session_factory, Ride) == 1


async def test_constraint_race_on_the_same_key_with_another_body_is_a_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory, stale_checks: Callable[[], None]
) -> None:
    passenger = await register_and_login(client, "pat")
    await order_ride(client, passenger, key="key-1")
    other_quote = await request_quote(client, passenger)
    stale_checks()

    response = await post_ride(client, passenger, other_quote["quote_id"], "key-1")

    assert response.status_code == 409
    assert error_code(response) == "idempotency_key_reused"
    assert await count_rows(session_factory, Ride) == 1


@pytest.mark.usefixtures("available_driver")
async def test_constraint_race_on_the_active_ride_is_a_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory, stale_checks: Callable[[], None]
) -> None:
    passenger = await register_and_login(client, "pat")
    await order_ride(client, passenger)
    other_quote = await request_quote(client, passenger)
    stale_checks()

    response = await post_ride(client, passenger, other_quote["quote_id"])

    assert response.status_code == 409
    assert error_code(response) == "active_ride_exists"
    assert await count_rows(session_factory, Ride) == 1


async def test_constraint_race_on_the_quote_is_a_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory, stale_checks: Callable[[], None]
) -> None:
    passenger = await register_and_login(client, "pat")
    quote = await request_quote(client, passenger)
    await post_ride(client, passenger, quote["quote_id"])
    async with session_factory.begin() as session:  # the first ride ended; its quote is spent
        await session.execute(update(Ride).values(status=RideStatus.CANCELLED))
    stale_checks()

    response = await post_ride(client, passenger, quote["quote_id"])

    assert response.status_code == 409
    assert error_code(response) == "quote_already_used"
    assert await count_rows(session_factory, Ride) == 1
