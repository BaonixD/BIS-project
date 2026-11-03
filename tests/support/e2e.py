"""Acceptance scenarios through the public API: one browser (HTTP client) per participant.

Usage in a test with the ``app``, ``session_factory`` and ``clock`` fixtures::

    async with open_town(app, session_factory, clock) as town:
        pat = await town.passenger("pat")
        dana = await town.driver("dana", location=NEAR_PICKUP)   # approved by the admin
        ride = await order(pat)                                  # quote + POST /rides
        [offer] = await offers(dana)
        expect(await answer(dana, offer["id"], "accept"))
        clock.advance(timedelta(seconds=30))
        await town.dispatch_step()        # what the background loop does every second

Each participant keeps its own cookies, as separate browsers would; the admin
account is created as ``scripts/create_admin.py`` does (``support.drivers.create_admin``).
After an application restart, ``town.reconnect(participant)`` gives the same user
a client of the new application with the old session cookie.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
from fastapi import FastAPI

from support.auth import LoggedInUser, current_session, login, register
from support.clock import ManualClock
from support.dispatch import OFFERS_URL, accept_url, reject_url
from support.drivers import (
    ADMIN_USERNAME,
    AVAILABILITY_URL,
    DRIVERS_ME_URL,
    LOCATION_URL,
    approve_url,
    complete_profile,
    create_admin,
)
from support.lifecycle import body_for, command_url
from support.payments import payment_url
from support.rides import QUOTE_BODY, QUOTES_URL, RIDES_URL, ride_body, ride_url
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides import dispatch
from taxi_service.modules.rides.idempotency import IDEMPOTENCY_HEADER

BASE_URL: Final = "https://testserver"
Json = dict[str, Any]


def expect(response: httpx.Response, status: int = 200) -> Json:
    """The JSON body of a response that must have ``status``."""
    assert response.status_code == status, response.text
    body: Json = response.json()
    return body


def expect_error(response: httpx.Response, status: int, code: str) -> Json:
    body = expect(response, status)
    assert body["error"]["code"] == code, body
    return body


async def eventually(check: Callable[[], Awaitable[bool]], *, timeout_s: float = 3.0) -> None:
    """Poll ``check`` every 10 ms until it holds (a running background loop)."""
    for _ in range(int(timeout_s / 0.01)):
        if await check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the expected state was not reached")


def only_item(page: Json) -> Json:
    """The single item of a list page."""
    [item] = page["items"]
    assert page["total"] == 1, page
    return item  # type: ignore[no-any-return]


@dataclass
class Participant:
    """A logged-in user with a browser of their own; writes carry the CSRF header."""

    client: httpx.AsyncClient
    user: LoggedInUser

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    async def get(self, url: str, **params: Any) -> httpx.Response:
        return await self.client.get(url, params=params)

    async def post(
        self, url: str, json: Json | None = None, *, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        return await self.client.post(
            url, json=json, headers={**self.user.csrf_headers, **(headers or {})}
        )

    async def put(self, url: str, json: Json) -> httpx.Response:
        return await self.client.put(url, json=json, headers=self.user.csrf_headers)

    async def patch(self, url: str, json: Json) -> httpx.Response:
        return await self.client.patch(url, json=json, headers=self.user.csrf_headers)


@dataclass
class Town:
    """Participants of one running application; see the module docstring."""

    app: FastAPI
    session_factory: SessionFactory
    clock: ManualClock
    stack: AsyncExitStack
    _admin: Participant | None = None
    _plates: int = field(default=0)

    async def browser(self) -> httpx.AsyncClient:
        """A new client of this application, closed when the town closes."""
        transport = httpx.ASGITransport(app=self.app)
        client = httpx.AsyncClient(transport=transport, base_url=BASE_URL)
        return await self.stack.enter_async_context(client)

    async def register(self, username: str, *, role: str = "passenger") -> Participant:
        client = await self.browser()
        expect(await register(client, username, role=role), 201)
        expect(await login(client, username))
        return Participant(client, await current_session(client))

    async def login(self, username: str) -> Participant:
        """An existing account (shared test ``PASSWORD``) in a browser of its own."""
        client = await self.browser()
        expect(await login(client, username))
        return Participant(client, await current_session(client))

    async def passenger(self, username: str) -> Participant:
        return await self.register(username)

    async def admin(self) -> Participant:
        """The admin (created on first use, outside the public API) in its own browser."""
        if self._admin is None:
            await create_admin(self.app, self.session_factory, self.clock)
            self._admin = await self.login(ADMIN_USERNAME)
        return self._admin

    async def driver(
        self, username: str, *, location: dict[str, float], online: bool = True
    ) -> Participant:
        """Register, fill in profile and car, get approved by the admin, report a location."""
        driver = await self.register(username, role="driver")
        self._plates += 1
        profile = complete_profile(f"{self._plates:03d}ETE02")
        assert expect(await driver.patch(DRIVERS_ME_URL, profile))["missing_fields"] == []
        admin = await self.admin()
        approved = expect(await admin.post(approve_url(driver.id)))
        assert approved["approval_status"] == "approved"
        expect(await driver.put(LOCATION_URL, location))
        if online:
            expect(await driver.put(AVAILABILITY_URL, {"online": True}))
        return driver

    async def reconnect(self, participant: Participant) -> Participant:
        """The same user in a client of this application, with the old session cookie."""
        client = await self.browser()
        for cookie in participant.client.cookies.jar:
            client.cookies.jar.set_cookie(cookie)
        return Participant(client, participant.user)

    async def dispatch_step(self) -> int:
        """One pass of the background loop, with the application's clock and policy."""
        state = self.app.state
        factory: SessionFactory = state.session_factory
        async with factory() as session:
            return await dispatch.process_due(
                session, clock=state.clock, policy=state.dispatch_policy
            )


@asynccontextmanager
async def open_town(
    app: FastAPI, session_factory: SessionFactory, clock: ManualClock
) -> AsyncIterator[Town]:
    """Run ``app``'s lifespan; every browser opened in the town closes before it ends."""
    async with app.router.lifespan_context(app), AsyncExitStack() as stack:
        yield Town(app, session_factory, clock, stack)


async def quote(passenger: Participant, body: Json | None = None) -> Json:
    return expect(await passenger.post(QUOTES_URL, body or QUOTE_BODY), 201)


async def create_ride(
    passenger: Participant, quote_id: str, key: str, payment_method: str | None = None
) -> httpx.Response:
    return await passenger.post(
        RIDES_URL, ride_body(quote_id, payment_method), headers={IDEMPOTENCY_HEADER: key}
    )


async def order(passenger: Participant, payment_method: str | None = None) -> Json:
    """A new quote, then a ride from it with a fresh ``Idempotency-Key`` (cash by default)."""
    quoted = await quote(passenger)
    key = uuid.uuid4().hex
    return expect(await create_ride(passenger, quoted["quote_id"], key, payment_method), 201)


async def offers(driver: Participant) -> list[Json]:
    """The driver's open offers (``GET /drivers/me/offers``)."""
    items: list[Json] = expect(await driver.get(OFFERS_URL))["items"]
    return items


async def answer(driver: Participant, offer_id: str, decision: str) -> httpx.Response:
    """``accept`` or ``reject`` an offer."""
    url = accept_url(offer_id) if decision == "accept" else reject_url(offer_id)
    return await driver.post(url)


async def ride_command(
    participant: Participant, ride_id: str, command: str, json: Json | None = None
) -> httpx.Response:
    """``arrive``, ``start``, ``complete``, ``cancel`` or ``release`` (with a reason by default)."""
    return await participant.post(command_url(ride_id, command), json or body_for(command))


async def ride(participant: Participant, ride_id: str) -> httpx.Response:
    return await participant.get(ride_url(ride_id))


async def payment(participant: Participant, ride_id: str) -> Json:
    return expect(await participant.get(payment_url(ride_id)))


async def cash_received(driver: Participant, ride_id: str) -> httpx.Response:
    """The assigned driver confirms the cash of a completed ride."""
    return await driver.post(payment_url(ride_id, "cash-received"))
