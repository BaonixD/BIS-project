from datetime import UTC, datetime, timedelta

DEFAULT_START = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


class ManualClock:
    """``Clock`` that moves only when a test calls :meth:`advance`."""

    def __init__(self, start: datetime = DEFAULT_START) -> None:
        if start.utcoffset() is None:
            raise ValueError("ManualClock requires a timezone-aware start")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("ManualClock cannot move backwards")
        self._now += delta
