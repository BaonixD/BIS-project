import asyncio
import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from taxi_service.modules.documents.service import fail

MAX_SIZE = 10 * 1024 * 1024


async def store_upload(file: UploadFile, root: Path) -> tuple[str, int, str]:
    await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True, mode=0o700)
    key = uuid.uuid4().hex + ".pdf"
    path = root / key
    try:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise fail("invalid_document", 422)
        size = 0
        digest = hashlib.sha256()
        with path.open("xb") as output:
            path.chmod(0o600)
            while chunk := await file.read(65536):
                if size == 0 and not chunk.startswith(b"%PDF-"):
                    raise fail("invalid_document", 422)
                size += len(chunk)
                if size > MAX_SIZE:
                    raise fail("document_too_large", 413)
                digest.update(chunk)
                await asyncio.to_thread(output.write, chunk)
        if size == 0:
            raise fail("invalid_document", 422)
        return key, size, digest.hexdigest()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def document_path(root: Path, key: str) -> Path:
    path = (root / key).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise fail("document_not_found", 404)
    return path
