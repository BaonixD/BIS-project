"""Report orphan PDF files; --delete removes only unreferenced files older than one day."""

import argparse
import asyncio
import time

from sqlalchemy import select

from taxi_service.core.config import Settings
from taxi_service.database.session import (
    create_database_engine,
    create_session_factory,
    read_transaction,
)
from taxi_service.modules.documents.models import DriverDocument


async def main(delete: bool) -> None:
    settings = Settings()
    engine = create_database_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as db, read_transaction(db):
            keys = set(await db.scalars(select(DriverDocument.storage_key)))
        count = 0
        for path in settings.document_storage_dir.glob("*.pdf"):
            if path.name in keys or path.stat().st_mtime > time.time() - 86400:
                continue
            count += 1
            if delete:
                path.unlink(missing_ok=True)
        print(f"Orphan files: {count}; mode: {'delete' if delete else 'dry-run'}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true")
    asyncio.run(main(parser.parse_args().delete))
