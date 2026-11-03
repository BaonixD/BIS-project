"""require_roles(...): 401 without a session, 403 forbidden for other roles."""

from typing import Annotated

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI

from support.auth import PASSWORD, login, register_and_login
from support.clock import ManualClock
from taxi_service.database.session import SessionFactory
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.users.models import UserRole
from taxi_service.modules.users.service import UserService

ADMIN_URL = "/_probe/admin"
DRIVER_URL = "/_probe/driver-work"

AdminUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.ADMIN))]
DriverOrAdmin = Annotated[
    AuthenticatedUser, Depends(require_roles(UserRole.DRIVER, UserRole.ADMIN))
]


def _probe_router() -> APIRouter:
    router = APIRouter()

    @router.get(ADMIN_URL)
    async def admin_only(user: AdminUser) -> dict[str, str]:
        return {"role": user.role}

    @router.post(DRIVER_URL)
    async def drivers_and_admins(user: DriverOrAdmin) -> dict[str, str]:
        return {"role": user.role}

    return router


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    app.include_router(_probe_router())
    return app


async def create_admin(app: FastAPI, session_factory: SessionFactory, clock: ManualClock) -> None:
    async with session_factory() as session:
        service = UserService(session, clock, app.state.password_hasher)
        await service.create_user(username="root", password=PASSWORD, role=UserRole.ADMIN)


def error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_role_check_needs_a_session_first(client: httpx.AsyncClient) -> None:
    response = await client.get(ADMIN_URL)

    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


@pytest.mark.parametrize("role", ["passenger", "driver"])
async def test_other_roles_are_forbidden(client: httpx.AsyncClient, role: str) -> None:
    await register_and_login(client, "alice", role=role)

    response = await client.get(ADMIN_URL)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


async def test_any_listed_role_is_allowed(client: httpx.AsyncClient) -> None:
    driver = await register_and_login(client, "dave", role="driver")

    response = await client.post(DRIVER_URL, headers=driver.csrf_headers)

    assert response.status_code == 200
    assert response.json() == {"role": "driver"}


async def test_passenger_is_forbidden_from_driver_command(client: httpx.AsyncClient) -> None:
    passenger = await register_and_login(client, "pat", role="passenger")

    response = await client.post(DRIVER_URL, headers=passenger.csrf_headers)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


async def test_role_check_keeps_csrf_protection(client: httpx.AsyncClient) -> None:
    await register_and_login(client, "dave", role="driver")

    response = await client.post(DRIVER_URL)

    assert response.status_code == 403
    assert error_code(response) == "csrf_failed"


async def test_admin_created_outside_the_api_can_log_in_and_pass(
    app: FastAPI, client: httpx.AsyncClient, session_factory: SessionFactory, clock: ManualClock
) -> None:
    await create_admin(app, session_factory, clock)
    assert (await login(client, "root")).status_code == 200

    assert (await client.get(ADMIN_URL)).json() == {"role": "admin"}
