from datetime import timedelta

from taxi_service.core.clock import Clock


class LoginAttemptLimiter:
    def __init__(
        self, *, clock: Clock, max_attempts: int, window: timedelta, max_keys: int
    ) -> None:
        self._clock = clock
        self._max_attempts = max_attempts
        self._window = window
        self._max_keys = max_keys

    def acquire(self, key: str) -> None:
        pass

    def reset(self, key: str) -> None:
        pass

    def __len__(self) -> int:
        return 0
