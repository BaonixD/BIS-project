"""Guards for destructive operations on database files (tests, future reset/seed)."""

import shutil
from pathlib import Path

from sqlalchemy.engine import make_url

SQLITE_SIDE_FILES = ("-wal", "-shm", "-journal")


class UnsafeDatabaseError(RuntimeError):
    """The database is not clearly disposable; refuse to delete or overwrite it."""


def disposable_sqlite_path(database_url: str, *, temp_root: Path) -> Path:
    url = make_url(database_url)
    assert url.database is not None
    return Path(url.database).resolve()


def replace_sqlite_database(source: Path, database_url: str, *, temp_root: Path) -> None:
    """Overwrite the target database with a copy of ``source`` (for example a template)."""
    target = disposable_sqlite_path(database_url, temp_root=temp_root)
    remove_sqlite_database(database_url, temp_root=temp_root)
    shutil.copyfile(source, target)


def remove_sqlite_database(database_url: str, *, temp_root: Path) -> None:
    """Delete the database file together with its WAL/SHM/journal files."""
    path = disposable_sqlite_path(database_url, temp_root=temp_root)
    for candidate in (path, *(path.with_name(path.name + suffix) for suffix in SQLITE_SIDE_FILES)):
        candidate.unlink(missing_ok=True)
