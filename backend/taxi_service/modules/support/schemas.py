import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["ride", "payment", "documents", "account", "other"]
TicketStatus = Literal["open", "in_progress", "resolved"]
SupportMode = Literal["ai", "human"]
AIState = Literal["idle", "pending", "running", "failed"]
AuthorKind = Literal["human", "assistant"]


class CreateTicket(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_request_id: uuid.UUID
    category: Category
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    ride_id: uuid.UUID | None = None


class SendMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_message_id: uuid.UUID
    body: str = Field(min_length=1, max_length=2000)


class MarkRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_read_seq: int = Field(ge=0)


class SetStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["in_progress", "resolved"]


class TicketView(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    owner_name: str
    ride_id: uuid.UUID | None
    category: Category
    subject: str
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    last_message_seq: int
    unread_count: int
    last_message: str
    support_mode: SupportMode
    ai_state: AIState
    ai_available: bool = Field(
        description="The assistant answers this ticket now; false when switched off or handed off."
    )


class MessageView(BaseModel):
    id: uuid.UUID
    seq: int
    author_kind: AuthorKind
    author_id: uuid.UUID | None = Field(description="Null for the assistant.")
    author_name: str
    author_role: str = Field(description="passenger, driver, admin or assistant.")
    body: str
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageView]
    has_more: bool


class AssistantStatus(BaseModel):
    available: bool = Field(description="New conversations are answered by the AI assistant first.")
