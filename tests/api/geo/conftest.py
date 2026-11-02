"""Fixtures of the geo API tests: no routing key ever comes from the environment."""

import os

import pytest


@pytest.fixture(autouse=True)
def _no_routing_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("ROUTING_"):
            monkeypatch.delenv(name)
    # An empty variable outranks a key in a developer's local .env file.
    monkeypatch.setenv("ROUTING_API_KEY", "")
