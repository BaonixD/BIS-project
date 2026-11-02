import json
import logging
import sys
from collections.abc import Iterator

import pytest

from taxi_service.core.config import Settings
from taxi_service.core.logging import (
    APP_LOGGER_NAME,
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
)
from taxi_service.main import create_app


def make_record(**extra: object) -> logging.LogRecord:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "taxi_service.test", logging.ERROR, __file__, 1, "failed %s", ("x",), exc_info
    )
    record.__dict__.update(extra)
    return record


@pytest.fixture
def app_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger(APP_LOGGER_NAME)
    saved = (list(logger.handlers), logger.level, logger.propagate)
    yield logger
    logger.handlers, logger.level, logger.propagate = saved[0], saved[1], saved[2]


def test_json_formatter_emits_structured_line() -> None:
    line = JsonFormatter().format(make_record(request_id="req-1"))

    payload = json.loads(line)
    assert payload["level"] == "ERROR"
    assert payload["logger"] == "taxi_service.test"
    assert payload["message"] == "failed x"
    assert payload["request_id"] == "req-1"
    assert payload["time"].endswith("+00:00")
    assert "ValueError: boom" in payload["exception"]


def test_filter_keeps_explicit_request_id() -> None:
    record = make_record(request_id="explicit")

    assert RequestIdFilter().filter(record)
    assert getattr(record, "request_id", None) == "explicit"


def test_filter_outside_request_sets_none() -> None:
    record = make_record()

    assert RequestIdFilter().filter(record)
    assert getattr(record, "request_id", "missing") is None


def test_configure_logging_is_idempotent(app_logger: logging.Logger) -> None:
    configure_logging("DEBUG")
    configure_logging("WARNING")

    assert len(app_logger.handlers) == 1
    assert isinstance(app_logger.handlers[0].formatter, JsonFormatter)
    assert app_logger.level == logging.WARNING
    assert app_logger.propagate is False


async def test_app_lifespan_configures_application_logger(app_logger: logging.Logger) -> None:
    app = create_app(Settings(_env_file=None, log_level="WARNING"))

    async with app.router.lifespan_context(app):
        assert app_logger.level == logging.WARNING
        assert isinstance(app_logger.handlers[0].formatter, JsonFormatter)
