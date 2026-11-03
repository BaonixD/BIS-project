import hashlib
import json
import re
from collections.abc import Mapping
from typing import Final

from pydantic import JsonValue

from taxi_service.modules.rides.exceptions import (
    IdempotencyKeyInvalidError,
    IdempotencyKeyRequiredError,
)
from taxi_service.modules.rides.models import IDEMPOTENCY_KEY_MAX_LENGTH

IDEMPOTENCY_HEADER: Final = "Idempotency-Key"
REPLAYED_HEADER: Final = "Idempotent-Replayed"

# Visible ASCII, no spaces: what clients put in a header without quoting or trimming.
_KEY_PATTERN: Final = re.compile(rf"[\x21-\x7e]{{1,{IDEMPOTENCY_KEY_MAX_LENGTH}}}")


def parse_idempotency_key(value: str | None) -> str:
    if value is None:
        raise IdempotencyKeyRequiredError
    if _KEY_PATTERN.fullmatch(value) is None:
        raise IdempotencyKeyInvalidError
    return value


def request_fingerprint(payload: Mapping[str, JsonValue]) -> str:
    """SHA-256 of canonical JSON (sorted keys, no whitespace, UTF-8): ADR 0005."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
