"""POST /api/v1/auth/register: passenger or driver accounts with validated credentials."""

import httpx
import pytest
from sqlalchemy import func, select

from support.auth import PASSWORD, REGISTER_URL, register
from support.clock import ManualClock
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.users.models import User


async def stored_users(session_factory: SessionFactory) -> list[User]:
    async with session_factory() as session, read_transaction(session):
        return list(await session.scalars(select(User).order_by(User.created_at)))


async def user_count(session_factory: SessionFactory) -> int:
    async with session_factory() as session, read_transaction(session):
        return (await session.scalar(select(func.count()).select_from(User))) or 0


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_register_creates_account_with_chosen_role(
    client: httpx.AsyncClient, clock: ManualClock, role: str
) -> None:
    response = await register(client, "Alice_01", role=role)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "username", "role", "created_at"}
    assert body["username"] == "Alice_01"
    assert body["role"] == role
    assert body["created_at"] == clock.now().isoformat().replace("+00:00", "Z")


async def test_password_is_stored_only_as_argon2id_hash(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    await register(client, "alice")

    [user] = await stored_users(session_factory)
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


async def test_username_taken_in_another_case_is_a_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    await register(client, "Alice")

    response = await register(client, "aLICE", role="driver")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_taken"
    [user] = await stored_users(session_factory)
    assert user.username == "Alice"


async def test_admin_cannot_be_registered_publicly(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    response = await register(client, "root", role="admin")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert await user_count(session_factory) == 0


async def test_role_is_required(client: httpx.AsyncClient) -> None:
    response = await client.post(REGISTER_URL, json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "username",
    ["ab", "a" * 33, "with space", "dash-name", "dot.name", "алия", "name\n", ""],
)
async def test_invalid_username_is_rejected(
    client: httpx.AsyncClient, session_factory: SessionFactory, username: str
) -> None:
    response = await register(client, username)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["errors"][0]["loc"] == ["body", "username"]
    assert await user_count(session_factory) == 0


@pytest.mark.parametrize("username", ["abc", "A" * 32, "user_42", "___"])
async def test_valid_username_boundaries_are_accepted(
    client: httpx.AsyncClient, username: str
) -> None:
    assert (await register(client, username)).status_code == 201


@pytest.mark.parametrize("password", ["p" * 9, "p" * 129])
async def test_password_length_outside_10_to_128_is_rejected(
    client: httpx.AsyncClient, password: str
) -> None:
    response = await register(client, "alice", password=password)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["errors"][0]["loc"] == ["body", "password"]
    assert password not in response.text


@pytest.mark.parametrize("password", ["p" * 10, "p" * 128])
async def test_password_length_boundaries_are_accepted(
    client: httpx.AsyncClient, password: str
) -> None:
    assert (await register(client, "alice", password=password)).status_code == 201
