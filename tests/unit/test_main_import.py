import importlib

import pytest

import taxi_service.main


def test_importing_main_does_not_read_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "not-a-level")

    module = importlib.reload(taxi_service.main)

    assert not hasattr(module, "app")
