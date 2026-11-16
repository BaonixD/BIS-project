import uuid
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession, read_transaction
from taxi_service.modules.auth.dependencies import AdminUser, CurrentUser
from taxi_service.modules.documents import service
from taxi_service.modules.documents.models import DocumentPackage, DriverDocument
from taxi_service.modules.documents.schemas import (
    DocumentKind,
    DocumentsSummary,
    PackageCommand,
    RequestDocuments,
    ReviewCommand,
)
from taxi_service.modules.documents.storage import document_path, store_upload
from taxi_service.modules.drivers.models import DriverProfile
from taxi_service.modules.drivers.router import DriverUser
from taxi_service.modules.users.models import UserRole

router = APIRouter(tags=["documents"])


@router.get("/drivers/me/documents")
async def mine(user: DriverUser, db: DbSession) -> DocumentsSummary:
    return await service.summary(db, user.id)


@router.get("/admin/drivers/{driver_id}/documents")
async def admin_documents(
    driver_id: uuid.UUID, _admin: AdminUser, db: DbSession, package_id: uuid.UUID | None = None
) -> DocumentsSummary:
    return await service.summary(db, driver_id, include_history=True, package_id=package_id)


@router.put("/drivers/me/documents/{kind}")
async def upload(
    kind: DocumentKind,
    file: UploadFile,
    user: DriverUser,
    db: DbSession,
    clock: ClockDep,
    request: Request,
) -> DocumentsSummary:
    root: Path = request.app.state.settings.document_storage_dir
    filename = Path((file.filename or "document.pdf").replace("\\", "/")).name[:255]
    key, size, sha256, pages = await store_upload(
        file, root, request.app.state.document_validation_limit
    )
    path = root / key
    try:
        await service.save_document(
            db,
            user.id,
            kind=kind,
            key=key,
            filename=filename,
            size=size,
            sha256=sha256,
            pages=pages,
            now=clock.now(),
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return await service.summary(db, user.id)


@router.delete("/drivers/me/documents/{kind}")
async def remove(
    kind: DocumentKind, user: DriverUser, db: DbSession, clock: ClockDep
) -> DocumentsSummary:
    async with db.begin():
        package = await service.editable(db, user.id, clock.now())
        doc = await db.scalar(
            select(DriverDocument).where(
                DriverDocument.package_id == package.id, DriverDocument.kind == kind
            )
        )
        if doc is not None:
            await db.delete(doc)
    return await service.summary(db, user.id)


@router.post("/drivers/me/documents/submit")
async def submit(
    body: PackageCommand, user: DriverUser, db: DbSession, clock: ClockDep
) -> DocumentsSummary:
    await service.change_package(db, user.id, body.package_id, body.version, "submit", clock.now())
    return await service.summary(db, user.id)


@router.post("/drivers/me/documents/revise")
async def revise(
    body: PackageCommand, user: DriverUser, db: DbSession, clock: ClockDep
) -> DocumentsSummary:
    await service.change_package(db, user.id, body.package_id, body.version, "revise", clock.now())
    return await service.summary(db, user.id)


@router.get("/documents/{document_id}/content")
async def content(
    document_id: uuid.UUID, user: CurrentUser, db: DbSession, request: Request
) -> FileResponse:
    async with read_transaction(db):
        found = (
            await db.execute(
                select(DriverDocument, DocumentPackage.driver_id)
                .join(DocumentPackage, DocumentPackage.id == DriverDocument.package_id)
                .where(DriverDocument.id == document_id)
            )
        ).one_or_none()
        if found is None or (user.role is not UserRole.ADMIN and found[1] != user.id):
            raise service.fail("document_not_found", 404)
        doc = found[0]
    path = document_path(request.app.state.settings.document_storage_dir, doc.storage_key)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="document.pdf",
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/admin/drivers/{driver_id}/documents/reject")
async def reject(
    driver_id: uuid.UUID, body: ReviewCommand, admin: AdminUser, db: DbSession, clock: ClockDep
) -> DocumentsSummary:
    reason = body.reason.strip()
    if not 3 <= len(reason) <= 500:
        raise service.fail("validation_error", 422)
    async with db.begin():
        package = await service.current(db, driver_id)
        if package is None or package.id != body.package_id or package.version != body.version:
            raise service.fail("document_version_conflict")
        if package.status == "rejected" and package.review_note == reason:
            pass
        elif package.status != "pending":
            raise service.fail("document_package_locked")
        else:
            package.status, package.review_note = "rejected", reason
            package.reviewed_at, package.reviewed_by = clock.now(), admin.id
    return await service.summary(db, driver_id)


@router.post("/admin/drivers/{driver_id}/documents/request")
async def request_documents(
    driver_id: uuid.UUID, body: RequestDocuments, _admin: AdminUser, db: DbSession, clock: ClockDep
) -> DocumentsSummary:
    from taxi_service.modules.drivers.models import ApprovalStatus
    from taxi_service.modules.rides.dispatch import revoke_driver_offers
    from taxi_service.modules.rides.service import driver_has_active_ride

    async with db.begin():
        profile = await db.get(DriverProfile, driver_id)
        if profile is None:
            raise service.fail("driver_not_found", 404)
        if await driver_has_active_ride(db, driver_id):
            raise service.fail("driver_on_active_ride")
        await service.profile_changed(db, profile, clock.now())
        package = await service.editable(db, driver_id, clock.now())
        package.review_note = body.reason
        profile.document_requirement_exempt = False
        profile.approval_status = ApprovalStatus.PENDING
        profile.approved_at = profile.approved_by = None
        profile.is_online = False
        await revoke_driver_offers(db, driver_id, clock.now())
    return await service.summary(db, driver_id, include_history=True)
