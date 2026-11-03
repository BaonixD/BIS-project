from pathlib import Path

import pytest

from taxi_service.database.safety import (
    UnsafeDatabaseError,
    disposable_sqlite_path,
    remove_sqlite_database,
    replace_sqlite_database,
)


def sqlite_url(path: Path | str) -> str:
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    root = tmp_path / "pytest-root"
    root.mkdir()
    return root


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    return directory


def test_file_inside_temp_root_is_disposable(temp_root: Path) -> None:
    path = temp_root / "case" / "app.db"

    assert disposable_sqlite_path(sqlite_url(path), temp_root=temp_root) == path.resolve()


@pytest.mark.parametrize(
    "name", ["taxi.db", "demo.db", "test.db", "t01-test.db", "test_t01.db", "Migrations.Test.db"]
)
def test_files_outside_temp_root_are_refused_whatever_their_name(
    temp_root: Path, outside: Path, name: str
) -> None:
    with pytest.raises(UnsafeDatabaseError):
        disposable_sqlite_path(sqlite_url(outside / name), temp_root=temp_root)


def test_project_database_is_refused(temp_root: Path) -> None:
    with pytest.raises(UnsafeDatabaseError):
        disposable_sqlite_path("sqlite+aiosqlite:///./taxi.db", temp_root=temp_root)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite://",
        "sqlite+aiosqlite:///:memory:",
        "postgresql+asyncpg://taxi@localhost/taxi_test",
    ],
)
def test_non_file_databases_are_refused(temp_root: Path, url: str) -> None:
    with pytest.raises(UnsafeDatabaseError):
        disposable_sqlite_path(url, temp_root=temp_root)


def test_remove_deletes_database_and_side_files(temp_root: Path) -> None:
    path = temp_root / "app.db"
    files = [path, temp_root / "app.db-wal", temp_root / "app.db-shm"]
    for file in files:
        file.write_bytes(b"x")

    remove_sqlite_database(sqlite_url(path), temp_root=temp_root)

    assert not any(file.exists() for file in files)


def test_remove_refuses_and_keeps_unsafe_file(temp_root: Path, outside: Path) -> None:
    keep = outside / "taxi.db"
    keep.write_bytes(b"data")

    with pytest.raises(UnsafeDatabaseError):
        remove_sqlite_database(sqlite_url(keep), temp_root=temp_root)

    assert keep.read_bytes() == b"data"


def test_replace_refuses_and_keeps_unsafe_file(temp_root: Path, outside: Path) -> None:
    template = temp_root / "template.db"
    template.write_bytes(b"template")
    keep = outside / "taxi.db"
    keep.write_bytes(b"data")

    with pytest.raises(UnsafeDatabaseError):
        replace_sqlite_database(template, sqlite_url(keep), temp_root=temp_root)

    assert keep.read_bytes() == b"data"


def test_replace_copies_template_over_disposable_file(temp_root: Path) -> None:
    template = temp_root / "template.db"
    template.write_bytes(b"template")
    target = temp_root / "case.db"
    target.write_bytes(b"old")
    (temp_root / "case.db-wal").write_bytes(b"old wal")

    replace_sqlite_database(template, sqlite_url(target), temp_root=temp_root)

    assert target.read_bytes() == b"template"
    assert not (temp_root / "case.db-wal").exists()
