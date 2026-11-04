import shutil
from pathlib import Path

from sqlalchemy.engine import make_url

SQLITE_SIDE_FILES = ("-wal", "-shm", "-journal")


class UnsafeDatabaseError(RuntimeError):
    pass


def disposable_sqlite_path(database_url: str, *, temp_root: Path) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        raise UnsafeDatabaseError("Only SQLite database files can be treated as disposable.")
    path = Path(url.database).resolve()
    if path.is_relative_to(temp_root.resolve()):
        return path
    raise UnsafeDatabaseError(f"Refusing to modify {path.name}: not inside the disposable root.")


def replace_sqlite_database(source: Path, database_url: str, *, temp_root: Path) -> None:
    target = disposable_sqlite_path(database_url, temp_root=temp_root)
    remove_sqlite_database(database_url, temp_root=temp_root)
    shutil.copyfile(source, target)


def remove_sqlite_database(database_url: str, *, temp_root: Path) -> None:
    path = disposable_sqlite_path(database_url, temp_root=temp_root)
    for candidate in (path, *(path.with_name(path.name + suffix) for suffix in SQLITE_SIDE_FILES)):
        candidate.unlink(missing_ok=True)
