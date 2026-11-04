from datetime import UTC, datetime
from typing import Annotated, Protocol

from fastapi import Depends, Request


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


ClockDep = Annotated[Clock, Depends(get_clock)]
