"""GET/PATCH /users/me: only the caller's own profile, only the allowed fields."""

from typing import Any

import httpx
import pytest

from support.auth import login, register_and_login

ME_URL = "/api/v1/users/me"


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_reading_the_profile_needs_a_session(client: httpx.AsyncClient) -> None:
    response = await client.get(ME_URL)

    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_new_account_has_an_empty_profile(client: httpx.AsyncClient, role: str) -> None:
    user = await register_and_login(client, "alice", role=role)

    response = await client.get(ME_URL)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "username": "alice",
        "role": role,
        "created_at": "2026-11-03T09:00:00Z",
        "display_name": None,
        "phone": None,
    }


async def test_update_changes_only_the_sent_fields(client: httpx.AsyncClient) -> None:
    user = await register_and_login(client, "alice")

    first = await client.patch(
        ME_URL, json={"display_name": "  Alice  "}, headers=user.csrf_headers
    )
    second = await client.patch(
        ME_URL, json={"phone": "+7 701 123-45-67"}, headers=user.csrf_headers
    )

    assert first.status_code == 200
    assert first.json()["display_name"] == "Alice"
    assert first.json()["phone"] is None
    assert second.status_code == 200
    assert (second.json()["display_name"], second.json()["phone"]) == ("Alice", "+77011234567")
    assert (await client.get(ME_URL)).json() == second.json()


async def test_update_needs_the_csrf_token(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "alice")

    response = await client.patch(ME_URL, json={"display_name": "Alice"})

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


@pytest.mark.parametrize(
    "body",
    [
        {"role": "admin"},
        {"role": "driver"},
        {"username": "mallory"},
        {"approval_status": "approved"},
        {"display_name": "Alice", "role": "admin"},
        {"password_hash": "x"},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_protected_or_unknown_fields_are_rejected(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    user = await register_and_login(client, "alice")

    response = await client.patch(ME_URL, json=body, headers=user.csrf_headers)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    profile = (await client.get(ME_URL)).json()
    assert (profile["role"], profile["username"], profile["display_name"]) == (
        "passenger",
        "alice",
        None,
    )


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": None},
        {"display_name": "   "},
        {"display_name": "x" * 65},
        {"phone": None},
        {"phone": "12345"},
        {"phone": "+7 701 abc 45 67"},
        {"phone": "+0123456789"},
        {"phone": "+7" + "1" * 15},
        {"phone": 77011234567},
    ],
)
async def test_invalid_values_are_rejected(client: httpx.AsyncClient, body: dict[str, Any]) -> None:
    user = await register_and_login(client, "alice")

    response = await client.patch(ME_URL, json=body, headers=user.csrf_headers)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_another_users_profile_is_neither_readable_nor_writable(
    client: httpx.AsyncClient,
) -> None:
    bob = await register_and_login(client, "bob")
    await client.patch(ME_URL, json={"display_name": "Bob"}, headers=bob.csrf_headers)
    alice = await register_and_login(client, "alice")

    by_id = await client.get(f"/api/v1/users/{bob.id}")
    with_id = await client.patch(
        ME_URL, json={"id": str(bob.id), "display_name": "Mallory"}, headers=alice.csrf_headers
    )
    renamed = await client.patch(ME_URL, json={"display_name": "Alice"}, headers=alice.csrf_headers)

    assert by_id.status_code == 404
    assert with_id.status_code == 422
    assert renamed.json()["id"] == str(alice.id)
    assert (await login(client, "bob")).status_code == 200
    assert (await client.get(ME_URL)).json()["display_name"] == "Bob"
