import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["ride", "payment", "documents", "account", "other"]
TicketStatus = Literal["open", "in_progress", "resolved"]


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


class MessageView(BaseModel):
    id: uuid.UUID
    seq: int
    author_id: uuid.UUID
    author_name: str
    author_role: str
    body: str
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageView]
    has_more: bool
