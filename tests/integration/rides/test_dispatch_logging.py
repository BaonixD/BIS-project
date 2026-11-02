"""A ride whose search step keeps failing does not flood the log every second.

The first failure of a series is logged with its traceback, the following ones
as a one-line warning; a successful step ends the series.
"""

import logging
from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from support.clock import ManualClock
from support.rides import PICKUP, RideFactory
from taxi_service.database.session import SessionFactory
from taxi_service.modules.rides.dispatch import DispatchService
from taxi_service.modules.rides.dispatch_loop import DispatchLoop
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY


class RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def dispatch_log() -> Iterator[RecordingHandler]:
    handler = RecordingHandler()
    logger = logging.getLogger("taxi_service.modules.rides.dispatch")
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


async def test_repeated_failures_of_one_ride_log_one_traceback_per_series(
    engine: AsyncEngine,
    session_factory: SessionFactory,
    clock: ManualClock,
    ride_factory: RideFactory,
    monkeypatch: pytest.MonkeyPatch,
    dispatch_log: RecordingHandler,
) -> None:
    await ride_factory.searching_ride(pickup=PICKUP)
    outcomes = iter(["fail", "fail", "ok", "fail"])

    async def scripted_step(self: DispatchService, ride: Ride, *args: object) -> None:
        if next(outcomes) == "fail":
            raise RuntimeError("step failed")
        # "ok": a successful step that leaves the ride searching, so it comes back

    monkeypatch.setattr(DispatchService, "_step", scripted_step)
    loop = DispatchLoop(
        session_factory,
        clock,
        DEFAULT_DISPATCH_POLICY,
        interval_s=1.0,
        database_url=engine.url,
    )

    for _ in range(4):
        assert await loop.run_once() == 1

    logged = [(record.levelno, record.exc_info is not None) for record in dispatch_log.records]
    assert logged == [
        (logging.ERROR, True),
        (logging.WARNING, False),
        (logging.ERROR, True),
    ]
