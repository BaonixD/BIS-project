import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.errors import AppError
from taxi_service.database.session import read_transaction
from taxi_service.modules.documents.models import DocumentPackage, DriverDocument
from taxi_service.modules.documents.schemas import DocumentsSummary, DocumentView, PackageView
from taxi_service.modules.drivers.models import DriverProfile, missing_fields
from taxi_service.modules.rides.dispatch import revoke_driver_offers
from taxi_service.modules.rides.service import driver_has_active_ride


def fail(code: str, status: int = 409) -> AppError:
    return AppError(status_code=status, code=code, message=code)


async def current(db: AsyncSession, driver_id: uuid.UUID) -> DocumentPackage | None:
    return await db.scalar(
        select(DocumentPackage)
        .where(DocumentPackage.driver_id == driver_id, DocumentPackage.status != "superseded")
        .with_for_update()
    )


async def editable(db: AsyncSession, driver_id: uuid.UUID, now: datetime) -> DocumentPackage:
    profile = await db.get(DriverProfile, driver_id)
    if profile is None:
        raise fail("driver_profile_incomplete")
    if await driver_has_active_ride(db, driver_id):
        raise fail("driver_on_active_ride")
    package = await current(db, driver_id)
    if package is None:
        version = (
            await db.scalar(
                select(func.max(DocumentPackage.version)).where(
                    DocumentPackage.driver_id == driver_id
                )
            )
            or 0
        ) + 1
        package = DocumentPackage(
            driver_id=driver_id,
            version=version,
            profile_revision=profile.profile_revision,
            status="draft",
            created_at=now,
        )
        db.add(package)
        await db.flush()
    if package.status != "draft":
        raise fail("document_package_locked")
    return package


async def summary(
    db: AsyncSession,
    driver_id: uuid.UUID,
    *,
    include_history: bool = False,
    package_id: uuid.UUID | None = None,
) -> DocumentsSummary:
    async with read_transaction(db):
        profile = await db.get(DriverProfile, driver_id)
        if profile is None:
            return DocumentsSummary(
                package=None,
                documents=[],
                missing_fields=missing_fields(None),
                legacy_exempt=False,
                can_submit=False,
            )
        packages = list(
            await db.scalars(
                select(DocumentPackage)
                .where(DocumentPackage.driver_id == driver_id)
                .order_by(DocumentPackage.version.desc())
                .limit(20)
            )
        )
        package = next((item for item in packages if item.status != "superseded"), None)
        if package_id is not None:
            selected = next((item for item in packages if item.id == package_id), None)
            if selected is None:
                raise fail("document_not_found", 404)
            package = selected
        documents = (
            []
            if package is None
            else list(
                await db.scalars(
                    select(DriverDocument).where(DriverDocument.package_id == package.id)
                )
            )
        )
        missing = missing_fields(profile)
        return DocumentsSummary(
            package=PackageView.model_validate(package) if package else None,
            documents=[
                DocumentView(
                    id=doc.id,
                    kind=doc.kind,
                    filename=doc.original_filename,
                    size_bytes=doc.size_bytes,
                    page_count=doc.page_count,
                    created_at=doc.created_at,
                )
                for doc in documents
            ],
            history=[PackageView.model_validate(item) for item in packages if item is not package]
            if include_history
            else [],
            missing_fields=missing,
            legacy_exempt=profile.document_requirement_exempt,
            can_submit=bool(
                package and package.status == "draft" and len(documents) == 2 and not missing
            ),
        )


async def change_package(
    db: AsyncSession,
    driver_id: uuid.UUID,
    package_id: uuid.UUID,
    version: int,
    action: str,
    now: datetime,
) -> None:
    async with db.begin():
        package = await current(db, driver_id)
        profile = await db.get(DriverProfile, driver_id)
        if (
            package is None
            or profile is None
            or package.id != package_id
            or package.version != version
        ):
            raise fail("document_version_conflict")
        if await driver_has_active_ride(db, driver_id):
            raise fail("driver_on_active_ride")
        if action == "submit":
            if package.status == "pending":
                return
            if package.status != "draft" or missing_fields(profile):
                raise fail("document_package_incomplete")
            count = await db.scalar(
                select(func.count())
                .select_from(DriverDocument)
                .where(DriverDocument.package_id == package.id)
            )
            if count != 2:
                raise fail("document_package_incomplete")
            package.status, package.submitted_at = "pending", now
        else:
            package.status = "superseded"
            await db.flush()
            new = await editable(db, driver_id, now)
            docs = list(
                await db.scalars(
                    select(DriverDocument).where(DriverDocument.package_id == package_id)
                )
            )
            for doc in docs:
                db.add(
                    DriverDocument(
                        package_id=new.id,
                        kind=doc.kind,
                        storage_key=doc.storage_key,
                        original_filename=doc.original_filename,
                        size_bytes=doc.size_bytes,
                        sha256=doc.sha256,
                        page_count=doc.page_count,
                        created_at=now,
                    )
                )
        profile.document_requirement_exempt = False
        profile.approval_status = type(profile.approval_status).PENDING
        profile.approved_at = profile.approved_by = None
        profile.is_online = False
        await revoke_driver_offers(db, driver_id, now)


async def approve_package(
    db: AsyncSession,
    profile: DriverProfile,
    package_id: uuid.UUID | None,
    version: int | None,
    admin_id: uuid.UUID,
    now: datetime,
) -> None:
    if profile.document_requirement_exempt and package_id is None:
        return
    package = await current(db, profile.user_id)
    if package is None or package_id is None or version is None:
        raise fail("document_package_not_submitted")
    if (
        package is None
        or package.id != package_id
        or package.version != version
        or package.profile_revision != profile.profile_revision
    ):
        raise fail("document_version_conflict")
    if package.status == "approved":
        return
    if package.status != "pending":
        raise fail("document_package_not_submitted")
    package.status, package.reviewed_at, package.reviewed_by = "approved", now, admin_id
    profile.document_requirement_exempt = False


async def profile_changed(db: AsyncSession, profile: DriverProfile, now: datetime) -> None:
    profile.profile_revision += 1
    profile.document_requirement_exempt = False
    package = await current(db, profile.user_id)
    if package is not None:
        await change_revision_in_transaction(db, profile, package, now)


async def change_revision_in_transaction(
    db: AsyncSession, profile: DriverProfile, old: DocumentPackage, now: datetime
) -> None:
    old.status = "superseded"
    await db.flush()
    package = await editable(db, profile.user_id, now)
    for doc in await db.scalars(select(DriverDocument).where(DriverDocument.package_id == old.id)):
        db.add(
            DriverDocument(
                package_id=package.id,
                kind=doc.kind,
                storage_key=doc.storage_key,
                original_filename=doc.original_filename,
                size_bytes=doc.size_bytes,
                sha256=doc.sha256,
                page_count=doc.page_count,
                created_at=now,
            )
        )


async def save_document(
    db: AsyncSession,
    driver_id: uuid.UUID,
    *,
    kind: str,
    key: str,
    filename: str,
    size: int,
    sha256: str,
    pages: int,
    now: datetime,
) -> None:
    async with db.begin():
        package = await editable(db, driver_id, now)
        existing = await db.scalar(
            select(DriverDocument).where(
                DriverDocument.package_id == package.id, DriverDocument.kind == kind
            )
        )
        if existing is not None:
            await db.delete(existing)
            await db.flush()
        db.add(
            DriverDocument(
                package_id=package.id,
                kind=kind,
                storage_key=key,
                original_filename=filename,
                size_bytes=size,
                sha256=sha256,
                page_count=pages,
                created_at=now,
            )
        )


async def require_reviewed(db: AsyncSession, profile: DriverProfile) -> None:
    if profile.document_requirement_exempt:
        return
    package = await current(db, profile.user_id)
    if (
        package is None
        or package.status != "approved"
        or package.profile_revision != profile.profile_revision
    ):
        raise fail("document_package_not_approved")
