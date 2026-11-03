"""Idempotency-Key format and the request fingerprint (ADR 0005)."""

import hashlib

import pytest

from taxi_service.core.errors import AppError
from taxi_service.modules.rides.idempotency import parse_idempotency_key, request_fingerprint

QUOTE_ID = "0b8f6f3e-6a55-4d71-9b8f-3c2a1e0d9c7b"


@pytest.mark.parametrize(
    "key", ["k", "x" * 128, "3f9c2b1e-7a6d-4e5f-8a9b-0c1d2e3f4a5b", "order#1:!~{}"]
)
def test_valid_key_is_returned_unchanged(key: str) -> None:
    assert parse_idempotency_key(key) == key


def test_missing_key_is_required() -> None:
    with pytest.raises(AppError) as raised:
        parse_idempotency_key(None)

    assert (raised.value.status_code, raised.value.code) == (422, "idempotency_key_required")


@pytest.mark.parametrize("key", ["", "x" * 129, "a b", " key", "ключ", "tab\tkey", "\x7f"])
def test_malformed_key_is_rejected(key: str) -> None:
    with pytest.raises(AppError) as raised:
        parse_idempotency_key(key)

    assert (raised.value.status_code, raised.value.code) == (422, "idempotency_key_invalid")
    assert raised.value.details == {}


def test_fingerprint_is_the_sha256_of_canonical_json() -> None:
    canonical = f'{{"quote_id":"{QUOTE_ID}"}}'

    assert (
        request_fingerprint({"quote_id": QUOTE_ID})
        == hashlib.sha256(canonical.encode()).hexdigest()
    )


def test_fingerprint_ignores_key_order_and_whitespace() -> None:
    first = request_fingerprint({"a": 1, "b": [1, 2], "c": {"y": None, "x": "z"}})
    second = request_fingerprint({"c": {"x": "z", "y": None}, "b": [1, 2], "a": 1})

    assert first == second
    assert len(first) == 64


def test_different_payloads_have_different_fingerprints() -> None:
    other = "0b8f6f3e-6a55-4d71-9b8f-3c2a1e0d9c7c"

    assert request_fingerprint({"quote_id": QUOTE_ID}) != request_fingerprint({"quote_id": other})
