"""The shared app fixture never talks to the real routing provider or reads a real key."""

import os

from fastapi import FastAPI

from support.routing import FakeRoutingProvider


def test_shared_app_uses_the_fake_routing_provider(app: FastAPI) -> None:
    assert isinstance(app.state.routing_provider_override, FakeRoutingProvider)


def test_routing_key_from_local_env_is_hidden_from_tests() -> None:
    assert os.environ.get("ROUTING_API_KEY") == ""
