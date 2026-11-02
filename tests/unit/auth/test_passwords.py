"""Argon2id password hashing through argon2-cffi, with light parameters for speed."""

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from taxi_service.core.config import Settings
from taxi_service.modules.auth.passwords import PasswordHasher

PASSWORD = "correct-horse-battery"


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher(time_cost=1, memory_kib=8, parallelism=1)


async def test_hash_is_argon2id_with_configured_parameters(hasher: PasswordHasher) -> None:
    password_hash = await hasher.hash(PASSWORD)

    assert password_hash.startswith("$argon2id$v=19$m=8,t=1,p=1$")
    assert PASSWORD not in password_hash


async def test_same_password_gets_a_new_salt_each_time(hasher: PasswordHasher) -> None:
    assert await hasher.hash(PASSWORD) != await hasher.hash(PASSWORD)


async def test_verify_accepts_only_the_original_password(hasher: PasswordHasher) -> None:
    password_hash = await hasher.hash(PASSWORD)

    assert await hasher.verify(password_hash, PASSWORD) is True
    assert await hasher.verify(password_hash, PASSWORD.upper()) is False


async def test_unknown_user_is_verified_against_a_dummy_hash(hasher: PasswordHasher) -> None:
    # A missing user still costs one Argon2 verification, so timing does not
    # reveal whether the username exists.
    assert await hasher.verify(None, PASSWORD) is False


async def test_malformed_stored_hash_never_verifies(hasher: PasswordHasher) -> None:
    assert await hasher.verify("not-an-argon2-hash", PASSWORD) is False


def test_settings_defaults_give_rfc_9106_parameters() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///./unused-test.db")

    hasher = PasswordHasher.from_settings(settings)

    assert (hasher.time_cost, hasher.memory_kib, hasher.parallelism) == (3, 65536, 4)


async def test_hashing_runs_at_most_max_concurrency_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = PasswordHasher(time_cost=1, memory_kib=8, parallelism=1, max_concurrency=2)
    running = 0
    peak = 0
    lock = threading.Lock()

    def slow_hash(password: str) -> str:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.02)
        with lock:
            running -= 1
        return password

    monkeypatch.setattr(hasher, "_hasher", SimpleNamespace(hash=slow_hash))

    await asyncio.gather(*(hasher.hash(f"password-{index}") for index in range(6)))

    assert peak == 2
