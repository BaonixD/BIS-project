from collections.abc import Mapping

from pydantic import JsonValue

IDEMPOTENCY_HEADER = "Idempotency-Key"


def parse_idempotency_key(value: str | None) -> str:
    raise NotImplementedError


def request_fingerprint(payload: Mapping[str, JsonValue]) -> str:
    raise NotImplementedError
