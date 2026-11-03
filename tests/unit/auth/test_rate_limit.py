"""In-memory login limiter: sliding window on the injected clock, bounded key storage."""

from datetime import timedelta

import pytest

from support.clock import ManualClock
from taxi_service.modules.auth.exceptions import TooManyLoginAttemptsError
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter

WINDOW = timedelta(minutes=15)


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


def limiter(
    clock: ManualClock, *, max_attempts: int = 3, max_keys: int = 100
) -> LoginAttemptLimiter:
    return LoginAttemptLimiter(
        clock=clock, max_attempts=max_attempts, window=WINDOW, max_keys=max_keys
    )


def use_up(subject: LoginAttemptLimiter, key: str, attempts: int) -> None:
    for _ in range(attempts):
        subject.acquire(key)


def test_attempts_beyond_the_limit_are_refused(clock: ManualClock) -> None:
    subject = limiter(clock)
    use_up(subject, "alice", 3)

    with pytest.raises(TooManyLoginAttemptsError) as error:
        subject.acquire("alice")

    assert error.value.status_code == 429
    assert error.value.code == "too_many_attempts"
    assert error.value.details == {"retry_after_seconds": int(WINDOW.total_seconds())}


def test_refused_attempts_do_not_extend_the_lockout(clock: ManualClock) -> None:
    subject = limiter(clock)
    use_up(subject, "alice", 3)
    clock.advance(timedelta(minutes=10))

    with pytest.raises(TooManyLoginAttemptsError) as error:
        subject.acquire("alice")

    assert error.value.details == {"retry_after_seconds": 5 * 60}


def test_window_slides_with_the_clock(clock: ManualClock) -> None:
    subject = limiter(clock)
    subject.acquire("alice")
    clock.advance(timedelta(minutes=5))
    use_up(subject, "alice", 2)

    clock.advance(WINDOW - timedelta(minutes=5))

    subject.acquire("alice")  # the first attempt has left the window
    with pytest.raises(TooManyLoginAttemptsError):
        subject.acquire("alice")


def test_reset_forgets_the_key(clock: ManualClock) -> None:
    subject = limiter(clock)
    use_up(subject, "alice", 3)

    subject.reset("alice")

    use_up(subject, "alice", 3)
    assert len(subject) == 1


def test_keys_are_limited_independently(clock: ManualClock) -> None:
    subject = limiter(clock)
    use_up(subject, "alice", 3)

    use_up(subject, "bob", 3)

    with pytest.raises(TooManyLoginAttemptsError):
        subject.acquire("alice")


def test_storage_is_bounded_by_evicting_the_least_recent_key(clock: ManualClock) -> None:
    subject = limiter(clock, max_keys=2)
    subject.acquire("alice")
    subject.acquire("bob")
    clock.advance(timedelta(seconds=1))
    subject.acquire("alice")

    subject.acquire("carol")

    assert len(subject) == 2
    use_up(subject, "bob", 3)  # bob was evicted, so the budget is fresh again


def test_expired_keys_are_dropped_before_evicting_active_ones(clock: ManualClock) -> None:
    subject = limiter(clock, max_keys=2)
    subject.acquire("old")
    clock.advance(WINDOW)
    use_up(subject, "alice", 3)

    subject.acquire("bob")

    assert len(subject) == 2
    with pytest.raises(TooManyLoginAttemptsError):
        subject.acquire("alice")
