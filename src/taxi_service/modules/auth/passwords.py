import asyncio
from functools import cached_property

import argon2
from argon2.exceptions import InvalidHashError, VerificationError

from taxi_service.core.config import Settings

# Hashed once per hasher; only its cost matters, the value never matches.
_DUMMY_PASSWORD = "dummy-password-for-unknown-users"


class PasswordHasher:
    """Argon2id hashing and verification (argon2-cffi), run off the event loop.

    Argon2 is deliberately slow and memory-hard, so every call is executed in a
    worker thread instead of blocking other requests.
    """

    def __init__(
        self, *, time_cost: int, memory_kib: int, parallelism: int, max_concurrency: int = 2
    ) -> None:
        self.time_cost = time_cost
        self.memory_kib = memory_kib
        self.parallelism = parallelism
        self.max_concurrency = max_concurrency
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
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str | None, password: str) -> bool:
        """Whether ``password`` matches ``password_hash``.

        ``None`` (no such user) is checked against a dummy hash of the same cost
        and always fails, so the response time does not reveal the username.
        """
        if password_hash is None:
            await asyncio.to_thread(self._verify_dummy, password)
            return False
        return await asyncio.to_thread(self._verify, password_hash, password)

    @cached_property
    def _dummy_hash(self) -> str:
        return self._hasher.hash(_DUMMY_PASSWORD)

    def _verify_dummy(self, password: str) -> None:
        # The first call also computes the dummy hash, still off the event loop.
        self._verify(self._dummy_hash, password)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
