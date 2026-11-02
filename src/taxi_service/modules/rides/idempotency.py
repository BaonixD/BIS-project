"""``Idempotency-Key`` format and request fingerprints (ADR 0005)."""

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Annotated, Final

from fastapi import Depends, Header
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
    """The key as sent; 422 ``idempotency_key_required`` / ``idempotency_key_invalid``."""
    if value is None:
        raise IdempotencyKeyRequiredError
    if _KEY_PATTERN.fullmatch(value) is None:
        raise IdempotencyKeyInvalidError
    return value


def request_fingerprint(payload: Mapping[str, JsonValue]) -> str:
    """SHA-256 (hex) of the payload as canonical JSON: sorted keys, no whitespace, UTF-8."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def get_idempotency_key(
    key: Annotated[
        str | None,
        Header(
            alias=IDEMPOTENCY_HEADER,
            description="Required. 1-128 visible ASCII characters, unique per new order "
            "(a UUID is a good choice). Repeat it to retry the same request safely.",
        ),
    ] = None,
) -> str:
    return parse_idempotency_key(key)


IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]
