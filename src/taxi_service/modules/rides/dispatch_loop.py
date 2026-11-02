"""The single background dispatch loop of the monolith (MVP_SPEC §6, ADR 0006).

An asyncio task started and stopped by the application lifespan. Every
``interval_s`` it runs ``DispatchService.process_due``: a read-only check, then
a short write transaction only for rides that need a step. The loop keeps no
state of its own: after a restart its first pass settles what ran out while the
application was down. No Celery, Redis or separate process.
"""

import asyncio
import contextlib
import logging

from sqlalchemy.engine import URL

from taxi_service.core.clock import Clock
from taxi_service.database.session import SessionFactory
from taxi_service.database.sqlite import sqlite_file_missing
from taxi_service.modules.rides.dispatch import DispatchService
from taxi_service.modules.rides.policy import DispatchPolicy

logger = logging.getLogger(__name__)


class DispatchLoop:
    def __init__(
        self,
        session_factory: SessionFactory,
        clock: Clock,
        policy: DispatchPolicy,
        *,
        interval_s: float,
        database_url: URL,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._session_factory = session_factory
        self._clock = clock
        self._policy = policy
        self._interval_s = interval_s
        self._database_url = database_url
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            raise RuntimeError("The dispatch loop is already running")
        self._task = asyncio.create_task(self._run(), name="dispatch-loop")

    async def stop(self) -> None:
        """Cancel the task and wait until it has finished."""
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def run_once(self) -> int:
        """One pass; how many rides needed a step. A missing SQLite file is not created."""
        if sqlite_file_missing(self._database_url):
            return 0
        async with self._session_factory() as session:
            return await DispatchService(session, self._clock, self._policy).process_due()

    async def _run(self) -> None:
        failing = False
        while True:
            try:
                await self.run_once()
            except Exception:
                # Log the first failure of a series with its traceback, then stay quiet.
                if not failing:
                    logger.exception("Dispatch pass failed; retrying every %ss", self._interval_s)
                failing = True
            else:
                if failing:
                    logger.info("Dispatch passes work again")
                failing = False
            await asyncio.sleep(self._interval_s)
