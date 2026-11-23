import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from taxi_service.database.base import Base, UtcDateTime


class Ticket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("owner_id", "client_request_id"),
        CheckConstraint("status IN ('open','in_progress','resolved')", name="status"),
        CheckConstraint(
            "category IN ('ride','payment','documents','account','other')", name="category"
        ),
        CheckConstraint("length(subject) BETWEEN 1 AND 120", name="subject"),
        CheckConstraint("last_message_seq >= 1", name="last_seq"),
        CheckConstraint(
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL)"
            " OR (status <> 'resolved' AND resolved_at IS NULL AND resolved_by IS NULL)",
            name="resolution",
        ),
        CheckConstraint("support_mode IN ('ai','human')", name="support_mode"),
        CheckConstraint("ai_state IN ('idle','pending','running','failed')", name="ai_state"),
        Index("ix_support_tickets_owner_updated", "owner_id", "updated_at"),
        Index("ix_support_tickets_status_updated", "status", "updated_at"),
        Index("ix_support_tickets_ai_state_updated", "ai_state", "updated_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    client_request_id: Mapped[uuid.UUID]
    fingerprint: Mapped[str] = mapped_column(String(64))
    ride_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rides.id"))
    category: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    last_message_seq: Mapped[int]
    support_mode: Mapped[str] = mapped_column(String(8), default="human", server_default="human")
    ai_state: Mapped[str] = mapped_column(String(8), default="idle", server_default="idle")
    ai_source_seq: Mapped[int | None]
    ai_started_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class Message(Base):
    __tablename__ = "support_messages"
    __table_args__ = (
        UniqueConstraint("ticket_id", "seq"),
        UniqueConstraint("author_id", "client_message_id"),
        UniqueConstraint("ticket_id", "ai_reply_to_seq"),
        CheckConstraint("seq >= 1", name="seq"),
        CheckConstraint("length(body) BETWEEN 1 AND 2000", name="body"),
        CheckConstraint(
            "(author_kind = 'human' AND author_id IS NOT NULL AND ai_reply_to_seq IS NULL)"
            " OR (author_kind = 'assistant' AND author_id IS NULL AND ai_reply_to_seq IS NOT NULL)",
            name="author",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"))
    seq: Mapped[int]
    author_kind: Mapped[str] = mapped_column(String(16), default="human", server_default="human")
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    ai_reply_to_seq: Mapped[int | None]
    client_message_id: Mapped[uuid.UUID]
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class ReadPosition(Base):
    __tablename__ = "support_reads"
    __table_args__ = (CheckConstraint("last_read_seq >= 0", name="last_seq"),)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_read_seq: Mapped[int]
