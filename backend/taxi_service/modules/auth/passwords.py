import asyncio
from collections.abc import Callable
from functools import cached_property

import argon2
from argon2.exceptions import InvalidHashError, VerificationError

from taxi_service.core.config import Settings

# Hashed once per hasher; only its cost matters, the value never matches.
_DUMMY_PASSWORD = "dummy-password-for-unknown-users"


class PasswordHasher:
    """Argon2id in worker threads, at most ``max_concurrency`` at once to bound memory."""

    def __init__(
        self, *, time_cost: int, memory_kib: int, parallelism: int, max_concurrency: int = 2
    ) -> None:
        self.time_cost = time_cost
        self.memory_kib = memory_kib
        self.parallelism = parallelism
        self._slots = asyncio.Semaphore(max_concurrency)
        self._hasher = argon2.PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_kib,
            parallelism=parallelism,
            type=argon2.Type.ID,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "PasswordHasher":
        return cls(
            time_cost=settings.password_hash_time_cost,
            memory_kib=settings.password_hash_memory_kib,
            parallelism=settings.password_hash_parallelism,
        )

    async def hash(self, password: str) -> str:
        return await self._run(self._hasher.hash, password)

    async def verify(self, password_hash: str | None, password: str) -> bool:
        """``None`` costs a dummy check, so timing does not reveal unknown usernames."""
        if password_hash is None:
            await self._run(self._verify_dummy, password)
            return False
        return await self._run(self._verify, password_hash, password)

    async def _run[**P, R](self, function: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        async with self._slots:
            return await asyncio.to_thread(function, *args, **kwargs)

    @cached_property
    def _dummy_hash(self) -> str:
        return self._hasher.hash(_DUMMY_PASSWORD)

    def _verify_dummy(self, password: str) -> None:
        self._verify(self._dummy_hash, password)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
