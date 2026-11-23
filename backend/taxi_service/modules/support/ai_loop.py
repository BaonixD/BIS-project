"""The single in-process assistant loop: one Gemini call at a time, state kept in the tickets.

The MVP runs one Uvicorn worker; a second worker would start a second loop.
"""

import asyncio
import contextlib
import logging
import time

from sqlalchemy.engine import URL

from taxi_service.core.clock import Clock
from taxi_service.database.session import SessionFactory
from taxi_service.database.sqlite import sqlite_file_missing
from taxi_service.modules.support import ai_service
from taxi_service.modules.support.ai_client import AIReplyError, SupportAIProvider
from taxi_service.modules.support.ai_config import SupportAISettings

logger = logging.getLogger(__name__)


class SupportAILoop:
    def __init__(
        self,
        session_factory: SessionFactory,
        clock: Clock,
        settings: SupportAISettings,
        provider: SupportAIProvider,
        *,
        database_url: URL,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._settings = settings
        self._provider = provider
        self._database_url = database_url
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            raise RuntimeError("The support AI loop is already running")
        self._task = asyncio.create_task(self._run(), name="support-ai-loop")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def recover(self) -> None:
        if sqlite_file_missing(self._database_url):
            return
        async with self._session_factory() as db:
            interrupted = await ai_service.recover_interrupted(db)
        if interrupted:
            logger.info("Support AI: %s interrupted replies marked failed", interrupted)

    async def run_once(self) -> bool:
        """Answer one pending ticket; False when there was nothing to do."""
        if sqlite_file_missing(self._database_url):
            return False
        async with self._session_factory() as db:
            claim = await ai_service.claim_next(db, self._clock)
            if claim is None:
                return False
            context = await ai_service.load_context(db, claim, self._settings.system_prompt)
        started = time.monotonic()
        text: str | None = None
        try:
            if context is None:
                raise AIReplyError("no_question")
            text = await self._provider.reply(system=context.system, turns=context.turns)
            code = "ok"
        except AIReplyError as error:
            code = error.code
        except Exception as error:  # a provider bug must not stop the loop
            code = f"unexpected_{type(error).__name__}"
        async with self._session_factory() as db:
            if text is None:
                outcome = await ai_service.fail_reply(db, claim)
            else:
                outcome = await ai_service.publish_reply(db, claim, text, self._clock)
        logger.info(
            "Support AI reply ticket=%s model=%s result=%s outcome=%s duration_ms=%d",
            claim.ticket_id,
            self._provider.model,
            code,
            outcome,
            (time.monotonic() - started) * 1000,
        )
        return True

    async def _run(self) -> None:
        try:
            await self.recover()
        except Exception:
            logger.exception("Support AI recovery failed")
        failing = False
        while True:
            worked = False
            try:
                worked = await self.run_once()
            except Exception:
                if not failing:
                    logger.exception("Support AI pass failed; retrying")
                failing = True
            else:
                if failing:
                    logger.info("Support AI passes work again")
                failing = False
            if not worked:
                await asyncio.sleep(self._settings.interval_s)
