import importlib
from pathlib import Path

import pytest

import taxi_service.database.metadata
import taxi_service.main


def test_importing_main_does_not_read_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "not-a-level")

    module = importlib.reload(taxi_service.main)

    assert not hasattr(module, "app")


def test_importing_app_and_metadata_touches_no_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database = tmp_path / "import-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")

    importlib.reload(taxi_service.database.metadata)
    app = importlib.reload(taxi_service.main).create_app()

    assert app.state.settings.database_url.endswith("import-test.db")
    assert not database.exists()
