import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime


class DocumentPackage(Base):
    __tablename__ = "driver_document_packages"
    __table_args__ = (
        UniqueConstraint("driver_id", "version"),
        CheckConstraint("version > 0 AND profile_revision > 0", name="version"),
        CheckConstraint("status <> 'pending' OR submitted_at IS NOT NULL", name="submitted"),
        CheckConstraint(
            "status NOT IN ('approved','rejected') OR (reviewed_at IS NOT NULL "
            "AND reviewed_by IS NOT NULL)",
            name="reviewed",
        ),
        CheckConstraint(
            "status IN ('draft','pending','approved','rejected','superseded')", name="status"
        ),
        Index(
            "uq_driver_document_packages_current",
            "driver_id",
            unique=True,
            sqlite_where=text("status <> 'superseded'"),
            postgresql_where=text("status <> 'superseded'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int]
    profile_revision: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(String(500))


class DriverDocument(Base):
    __tablename__ = "driver_documents"
    __table_args__ = (
        UniqueConstraint("package_id", "kind"),
        CheckConstraint("kind IN ('identity_card','driver_license')", name="kind"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="size"),
        CheckConstraint("page_count BETWEEN 1 AND 10", name="page_count"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("driver_document_packages.id"))
    kind: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(String(40))
    original_filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
