import json
import logging
import sys
from datetime import UTC, datetime

from taxi_service.core.request_id import current_request_id

APP_LOGGER_NAME = "taxi_service"


class RequestIdFilter(logging.Filter):
    """Adds the current request ID unless the caller already passed one in ``extra``."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = current_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time (UTC), level, logger, message, request_id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Configure the application logger; safe to call repeatedly."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
