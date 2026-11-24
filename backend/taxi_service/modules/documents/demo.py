"""Synthetic blank demo PDFs, submitted through the same storage and package services."""

import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from taxi_service.core.clock import Clock
from taxi_service.modules.documents import service
from taxi_service.modules.documents.schemas import PackageCommand
from taxi_service.modules.documents.storage import store_upload


async def submit_demo_package(
    db: AsyncSession, driver_id: uuid.UUID, clock: Clock, root: Path
) -> PackageCommand:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.add_metadata({"/Title": "TulparTaxi DEMO - no personal data"})
    buffer = io.BytesIO()
    writer.write(buffer)
    data = buffer.getvalue()
    for kind in ["identity_card", "driver_license"]:
        file = UploadFile(
            file=io.BytesIO(data),
            filename="demo.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )
        key, size, sha256 = await store_upload(file, root)
        try:
            await service.save_document(
                db,
                driver_id,
                kind=kind,
                key=key,
                filename="demo.pdf",
                size=size,
                sha256=sha256,
                now=clock.now(),
            )
        except BaseException:
            (root / key).unlink(missing_ok=True)
            raise
    result = await service.summary(db, driver_id)
    assert result.package is not None
    await service.change_package(
        db, driver_id, result.package.id, result.package.version, "submit", clock.now()
    )
    return PackageCommand(package_id=result.package.id, version=result.package.version)
