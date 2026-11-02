from datetime import UTC, datetime, timedelta

from taxi_service.core.clock import Clock, SystemClock


def test_system_clock_returns_aware_utc_now() -> None:
    clock: Clock = SystemClock()

    before = datetime.now(UTC)
    now = clock.now()
    after = datetime.now(UTC)

    assert now.utcoffset() == timedelta(0)
    assert before <= now <= after
