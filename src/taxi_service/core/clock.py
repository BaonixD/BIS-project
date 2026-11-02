"""Server time for business rules: one injectable source instead of ``datetime.now()``.

Session expiry, rate limiting and later offer deadlines read the time through a
``Clock`` so tests can move it explicitly instead of sleeping.
"""

from datetime import UTC, datetime
from typing import Annotated, Protocol

from fastapi import Depends, Request


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as a timezone-aware UTC ``datetime``."""
        ...


class SystemClock:
    """Wall-clock time of this machine, in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def get_clock(request: Request) -> Clock:
    """FastAPI dependency: the application's clock from ``app.state.clock``."""
    clock: Clock = request.app.state.clock
    return clock


ClockDep = Annotated[Clock, Depends(get_clock)]
