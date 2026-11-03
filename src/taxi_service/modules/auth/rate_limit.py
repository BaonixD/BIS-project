import math
from collections import OrderedDict, deque
from datetime import datetime, timedelta

from taxi_service.core.clock import Clock
from taxi_service.core.config import Settings
from taxi_service.modules.auth.exceptions import TooManyLoginAttemptsError


class LoginAttemptLimiter:
    """Sliding-window limit per key in one process and event loop, lost on restart (ADR 0003)."""

    def __init__(
        self, *, clock: Clock, max_attempts: int, window: timedelta, max_keys: int
    ) -> None:
        self._clock = clock
        self._max_attempts = max_attempts
        self._window = window
        self._max_keys = max_keys
        self._attempts: OrderedDict[str, deque[datetime]] = OrderedDict()

    @classmethod
    def from_settings(cls, settings: Settings, clock: Clock) -> "LoginAttemptLimiter":
        return cls(
            clock=clock,
            max_attempts=settings.login_max_attempts,
            window=timedelta(seconds=settings.login_attempt_window_seconds),
            max_keys=settings.login_limiter_max_keys,
        )

    def acquire(self, key: str) -> None:
        now = self._clock.now()
        attempts = self._attempts.get(key)
        if attempts is not None:
            self._drop_expired(attempts, now)
            if len(attempts) >= self._max_attempts:
                raise TooManyLoginAttemptsError(self._retry_after_seconds(attempts[0], now))
        else:
            self._make_room(now)
            attempts = deque(maxlen=self._max_attempts)
            self._attempts[key] = attempts
        attempts.append(now)
        self._attempts.move_to_end(key)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def __len__(self) -> int:
        return len(self._attempts)

    def _drop_expired(self, attempts: deque[datetime], now: datetime) -> None:
        while attempts and attempts[0] <= now - self._window:
            attempts.popleft()

    def _make_room(self, now: datetime) -> None:
        if len(self._attempts) < self._max_keys:
            return
        for key, attempts in list(self._attempts.items()):
            self._drop_expired(attempts, now)
            if not attempts:
                del self._attempts[key]
        while len(self._attempts) >= self._max_keys:
            self._attempts.popitem(last=False)

    def _retry_after_seconds(self, oldest: datetime, now: datetime) -> int:
        return max(1, math.ceil((oldest + self._window - now).total_seconds()))
