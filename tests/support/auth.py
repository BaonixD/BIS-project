"""Register and log in through the real API; the client keeps the session cookie.

Usage in a test with the ``client`` fixture::

    user = await register_and_login(client, "driver_1", role="driver")
    await client.post("/api/v1/...", json=..., headers=user.csrf_headers)
"""

import uuid
from dataclasses import dataclass

import httpx

AUTH_PREFIX = "/api/v1/auth"
REGISTER_URL = f"{AUTH_PREFIX}/register"
LOGIN_URL = f"{AUTH_PREFIX}/login"
LOGOUT_URL = f"{AUTH_PREFIX}/logout"
SESSION_URL = f"{AUTH_PREFIX}/session"
SESSION_COOKIE = "taxi_session"
CSRF_HEADER = "X-CSRF-Token"
PASSWORD = "correct-horse-battery"


@dataclass(frozen=True)
class LoggedInUser:
    id: uuid.UUID
    username: str
    role: str
    csrf_token: str

    @property
    def csrf_headers(self) -> dict[str, str]:
        """Header required on every state-changing request with the session cookie."""
        return {CSRF_HEADER: self.csrf_token}


async def register(
    client: httpx.AsyncClient, username: str, *, password: str = PASSWORD, role: str = "passenger"
) -> httpx.Response:
    return await client.post(
        REGISTER_URL, json={"username": username, "password": password, "role": role}
    )


async def login(
    client: httpx.AsyncClient, username: str, *, password: str = PASSWORD
) -> httpx.Response:
    return await client.post(LOGIN_URL, json={"username": username, "password": password})


async def register_and_login(
    client: httpx.AsyncClient, username: str, *, role: str = "passenger", password: str = PASSWORD
) -> LoggedInUser:
    registered = await register(client, username, password=password, role=role)
    assert registered.status_code == 201, registered.text
    logged_in = await login(client, username, password=password)
    assert logged_in.status_code == 200, logged_in.text
    return await current_session(client)


async def current_session(client: httpx.AsyncClient) -> LoggedInUser:
    """``GET /auth/session`` of the client's cookie: the user and the CSRF token."""
    response = await client.get(SESSION_URL)
    assert response.status_code == 200, response.text
    body = response.json()
    return LoggedInUser(
        id=uuid.UUID(body["user"]["id"]),
        username=body["user"]["username"],
        role=body["user"]["role"],
        csrf_token=body["csrf_token"],
    )
