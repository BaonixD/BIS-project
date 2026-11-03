"""Two simultaneous registrations of one username: the database picks one winner.

Each request has its own session and SQLite connection; both pass the Python
validation, so only the unique constraint can reject the second one.
"""

import asyncio

import httpx
from sqlalchemy import select

from support.auth import register
from taxi_service.database.session import SessionFactory, read_transaction
from taxi_service.modules.users.models import User


async def test_concurrent_registration_gives_one_created_and_one_conflict(
    client: httpx.AsyncClient, session_factory: SessionFactory
) -> None:
    responses = await asyncio.gather(
        register(client, "Racer", role="passenger"),
        register(client, "rACER", role="driver"),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    [conflict] = [response for response in responses if response.status_code == 409]
    assert conflict.json()["error"]["code"] == "username_taken"
    async with session_factory() as session, read_transaction(session):
        usernames = list(await session.scalars(select(User.username)))
    assert len(usernames) == 1
