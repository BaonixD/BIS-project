"""Synthetic document fixtures for domains that require an approved driver."""

import hashlib
import io
import uuid

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from support.clock import ManualClock
from taxi_service.database.session import SessionFactory
from taxi_service.modules.documents.models import DocumentPackage, DriverDocument
from taxi_service.modules.drivers.models import DriverProfile


def pdf_bytes(*, active: bool = False, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    if active:
        writer.root_object[NameObject("/OpenAction")] = DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert(1)"),
            }
        )
    if encrypted:
        writer.encrypt("password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


async def pending_package(
    session_factory: SessionFactory, driver_id: uuid.UUID, clock: ManualClock
) -> tuple[uuid.UUID, int]:
    async with session_factory.begin() as db:
        profile = await db.get(DriverProfile, driver_id)
        assert profile is not None
        package = DocumentPackage(
            driver_id=driver_id,
            version=1,
            profile_revision=profile.profile_revision,
            status="pending",
            created_at=clock.now(),
            submitted_at=clock.now(),
        )
        db.add(package)
        await db.flush()
        data = pdf_bytes()
        for kind in ["identity_card", "driver_license"]:
            db.add(
                DriverDocument(
                    package_id=package.id,
                    kind=kind,
                    storage_key=uuid.uuid4().hex + ".pdf",
                    original_filename="fixture.pdf",
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    page_count=1,
                    created_at=clock.now(),
                )
            )
    return package.id, package.version


async def submit_http(client, csrf_headers):
    data = pdf_bytes()
    for kind in ["identity_card", "driver_license"]:
        response = await client.put(
            f"/api/v1/drivers/me/documents/{kind}",
            files={"file": ("fixture.pdf", data, "application/pdf")},
            headers=csrf_headers,
        )
        assert response.status_code == 200, response.text
    package = response.json()["package"]
    response = await client.post(
        "/api/v1/drivers/me/documents/submit",
        json={"package_id": package["id"], "version": package["version"]},
        headers=csrf_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["package"]
