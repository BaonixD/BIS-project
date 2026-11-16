import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PackageStatus = Literal["draft", "pending", "approved", "rejected", "superseded"]
DocumentKind = Literal["identity_card", "driver_license"]


class PackageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    status: PackageStatus
    review_note: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None


class DocumentView(BaseModel):
    id: uuid.UUID
    kind: DocumentKind
    filename: str
    size_bytes: int
    page_count: int
    created_at: datetime


class DocumentsSummary(BaseModel):
    package: PackageView | None
    documents: list[DocumentView]
    history: list[PackageView] = []
    missing_fields: list[str]
    legacy_exempt: bool
    can_submit: bool


class PackageCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_id: uuid.UUID
    version: int = Field(ge=1)


class ReviewCommand(PackageCommand):
    reason: str = Field(min_length=3, max_length=500)


class RequestDocuments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)
