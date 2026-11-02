"""Request-scoped session: bound to the app's database, closed after the request,
and never committed implicitly (the service owns the transaction)."""

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.database.session import SessionDep, SessionFactory

seen_sessions: list[AsyncSession] = []


def _probe_router() -> APIRouter:
    router = APIRouter(prefix="/_probe")

    @router.post("/uncommitted/{value}")
    async def write_without_commit(value: int, session: SessionDep) -> dict[str, int]:
        seen_sessions.append(session)
        await session.execute(text("INSERT INTO probe (value) VALUES (:value)"), {"value": value})
        return {"value": value}

    @router.post("/committed/{value}")
    async def write_in_transaction(value: int, session: SessionDep) -> dict[str, int]:
        seen_sessions.append(session)
        async with session.begin():
            await session.execute(
                text("INSERT INTO probe (value) VALUES (:value)"), {"value": value}
            )
        return {"value": value}

    return router


@pytest.fixture
async def app(app: FastAPI, session_factory: SessionFactory) -> FastAPI:
    seen_sessions.clear()
    async with session_factory.begin() as session:
        await session.execute(text("CREATE TABLE probe (value INTEGER NOT NULL)"))
    app.include_router(_probe_router())
    return app


async def stored_values(session_factory: SessionFactory) -> list[int]:
    async with session_factory() as session:
        return list(await session.scalars(text("SELECT value FROM probe ORDER BY value")))


async def test_session_is_not_committed_implicitly(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    response = await client.post("/_probe/uncommitted/1")

    assert response.status_code == 200
    assert await stored_values(session_factory) == []


async def test_service_transaction_is_committed(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    response = await client.post("/_probe/committed/2")

    assert response.status_code == 200
    assert await stored_values(session_factory) == [2]


async def test_each_request_gets_a_new_session_that_is_closed(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await client.post("/_probe/committed/3")
    await client.post("/_probe/uncommitted/4")

    first, second = seen_sessions
    assert first is not second
    assert not first.in_transaction()
    assert not second.in_transaction()
    assert app.state.engine.pool.checkedout() == 0
