import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Final

from sqlalchemy import ColumnElement, RowMapping, Select, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from taxi_service.core.clock import Clock
from taxi_service.core.errors import AppError
from taxi_service.database.search import matches_text
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.support.ai_config import SupportAISettings
from taxi_service.modules.support.models import Message, ReadPosition, Ticket
from taxi_service.modules.support.schemas import (
    CreateTicket,
    MessagePage,
    MessageView,
    SendMessage,
    TicketView,
)
from taxi_service.modules.users.models import User, UserRole
from taxi_service.schemas.pagination import Page

ASSISTANT_NAME: Final = "ИИ-помощник"
ACTIVE_AI_STATES: Final = ("pending", "running")


def fail(code: str, status: int = 409) -> AppError:
    return AppError(status_code=status, code=code, message=code)


def visible(user: AuthenticatedUser) -> ColumnElement[bool]:
    return Ticket.id.is_not(None) if user.role is UserRole.ADMIN else Ticket.owner_id == user.id


def acquire(limiter: LoginAttemptLimiter, user: AuthenticatedUser) -> None:
    try:
        limiter.acquire(str(user.id))
    except AppError as error:
        raise AppError(
            status_code=429,
            code="support_rate_limited",
            message="Please wait before sending again.",
            details=error.details,
        ) from None


async def lock_ticket(db: AsyncSession, ticket_id: uuid.UUID, user: AuthenticatedUser) -> Ticket:
    ticket = await db.scalar(
        select(Ticket).where(Ticket.id == ticket_id, visible(user)).with_for_update()
    )
    if ticket is None:
        raise fail("support_not_found", 404)
    return ticket


def ticket_select(
    user: AuthenticatedUser,
) -> Select[
    uuid.UUID,
    uuid.UUID,
    str,
    uuid.UUID | None,
    str,
    str,
    str,
    datetime,
    datetime,
    int,
    int,
    str,
    str,
    str,
]:
    last_read = (
        select(ReadPosition.last_read_seq)
        .where(ReadPosition.ticket_id == Ticket.id, ReadPosition.user_id == user.id)
        .correlate(Ticket)
        .scalar_subquery()
    )
    unread = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.ticket_id == Ticket.id,
            or_(Message.author_id.is_(None), Message.author_id != user.id),
            Message.seq > func.coalesce(last_read, 0),
        )
        .correlate(Ticket)
        .scalar_subquery()
    )
    latest = (
        select(Message.body)
        .where(Message.ticket_id == Ticket.id)
        .order_by(Message.seq.desc())
        .limit(1)
        .correlate(Ticket)
        .scalar_subquery()
    )
    return (
        select(
            Ticket.id,
            Ticket.owner_id,
            User.username.label("owner_name"),
            Ticket.ride_id,
            Ticket.category,
            Ticket.subject,
            Ticket.status,
            Ticket.created_at,
            Ticket.updated_at,
            Ticket.last_message_seq,
            unread.label("unread_count"),
            latest.label("last_message"),
            Ticket.support_mode,
            Ticket.ai_state,
        )
        .join(User, User.id == Ticket.owner_id)
        .where(visible(user))
    )


def ticket_view(row: RowMapping, ai_active: bool) -> TicketView:
    available = ai_active and row["support_mode"] == "ai"
    return TicketView.model_validate({**row, "ai_available": available})


async def read_ticket(
    db: AsyncSession, ticket_id: uuid.UUID, user: AuthenticatedUser, *, ai_active: bool
) -> TicketView:
    async with read_transaction(db):
        row = (
            (await db.execute(ticket_select(user).where(Ticket.id == ticket_id)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise fail("support_not_found", 404)
        return ticket_view(row, ai_active)


async def list_tickets(
    db: AsyncSession,
    user: AuthenticatedUser,
    *,
    status: str | None,
    category: str | None,
    query: str,
    limit: int,
    offset: int,
    ai_active: bool,
) -> Page[TicketView]:
    conditions: list[ColumnElement[bool]] = []
    if status:
        conditions.append(Ticket.status == status)
    if category:
        conditions.append(Ticket.category == category)
    if query.strip():
        conditions.append(matches_text(query, Ticket.subject, User.username))
    statement = ticket_select(user).where(*conditions)
    async with read_transaction(db):
        rows = (
            (
                await db.execute(
                    statement.order_by(Ticket.updated_at.desc(), Ticket.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .mappings()
            .all()
        )
        total = await db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    return Page(
        items=[ticket_view(row, ai_active) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def create_ticket(
    db: AsyncSession,
    user: AuthenticatedUser,
    data: CreateTicket,
    *,
    clock: Clock,
    limiter: LoginAttemptLimiter,
    ai: SupportAISettings,
) -> TicketView:
    fingerprint = hashlib.sha256(
        json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    async with db.begin():
        ticket = await db.scalar(
            select(Ticket).where(
                Ticket.owner_id == user.id, Ticket.client_request_id == data.client_request_id
            )
        )
        if ticket is not None:
            if ticket.fingerprint != fingerprint:
                raise fail("support_request_conflict")
        else:
            acquire(limiter, user)
            if data.ride_id is not None:
                ride = await db.get(Ride, data.ride_id)
                if ride is None or user.id not in (ride.passenger_id, ride.driver_id):
                    raise fail("ride_not_found", 404)
            now = clock.now()
            ticket = Ticket(
                owner_id=user.id,
                client_request_id=data.client_request_id,
                fingerprint=fingerprint,
                ride_id=data.ride_id,
                category=data.category,
                subject=data.subject,
                status="open",
                created_at=now,
                updated_at=now,
                last_message_seq=1,
                support_mode="ai" if ai.active else "human",
                ai_state="idle",
            )
            db.add(ticket)
            await db.flush()
            db.add(
                Message(
                    ticket_id=ticket.id,
                    seq=1,
                    author_id=user.id,
                    client_message_id=data.client_request_id,
                    body=data.body,
                    created_at=now,
                )
            )
            db.add(ReadPosition(ticket_id=ticket.id, user_id=user.id, last_read_seq=1))
            await db.flush()
            if ai.active:
                await queue_ai_reply(db, ticket.id, 1, limit=ai.queue_limit)
    return await read_ticket(db, ticket.id, user, ai_active=ai.active)


async def messages(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: AuthenticatedUser,
    *,
    after_seq: int | None,
    before_seq: int | None,
    limit: int,
) -> MessagePage:
    from taxi_service.modules.support.schemas import MessagePage

    if after_seq is not None and before_seq is not None:
        raise fail("validation_error", 422)
    async with read_transaction(db):
        exists = await db.scalar(select(Ticket.id).where(Ticket.id == ticket_id, visible(user)))
        if exists is None:
            raise fail("support_not_found", 404)
        query = (
            select(
                Message.id,
                Message.seq,
                Message.author_kind,
                Message.author_id,
                User.username,
                User.role,
                Message.body,
                Message.created_at,
            )
            .outerjoin(User, User.id == Message.author_id)
            .where(Message.ticket_id == ticket_id)
        )
        if after_seq is not None:
            query = query.where(Message.seq > after_seq).order_by(Message.seq)
        else:
            if before_seq is not None:
                query = query.where(Message.seq < before_seq)
            query = query.order_by(Message.seq.desc())
        rows = list((await db.execute(query.limit(limit + 1))).mappings().all())
    more = len(rows) > limit
    rows = rows[:limit]
    if after_seq is None:
        rows.reverse()
    return MessagePage(items=[message_view(row) for row in rows], has_more=more)


def message_view(row: RowMapping) -> MessageView:
    assistant = row["author_kind"] == "assistant"
    return MessageView(
        id=row["id"],
        seq=row["seq"],
        author_kind=row["author_kind"],
        author_id=row["author_id"],
        author_name=ASSISTANT_NAME if assistant else row["username"],
        author_role="assistant" if assistant else UserRole(row["role"]).value,
        body=row["body"],
        created_at=row["created_at"],
    )


async def send_message(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: AuthenticatedUser,
    data: SendMessage,
    *,
    clock: Clock,
    limiter: LoginAttemptLimiter,
    ai: SupportAISettings,
) -> MessageView:
    from taxi_service.modules.support.schemas import MessageView

    async with db.begin():
        ticket = await lock_ticket(db, ticket_id, user)
        message = await db.scalar(
            select(Message).where(
                Message.author_id == user.id, Message.client_message_id == data.client_message_id
            )
        )
        if message is not None:
            if message.ticket_id != ticket_id or message.body != data.body:
                raise fail("support_request_conflict")
        else:
            acquire(limiter, user)
            now = clock.now()
            ticket.last_message_seq += 1
            ticket.updated_at = now
            ticket.status = (
                "in_progress"
                if user.role is UserRole.ADMIN
                else "open"
                if ticket.status == "resolved"
                else ticket.status
            )
            ticket.resolved_at = ticket.resolved_by = None
            if user.role is UserRole.ADMIN:
                hand_to_human(ticket)
            message = Message(
                ticket_id=ticket_id,
                seq=ticket.last_message_seq,
                author_id=user.id,
                client_message_id=data.client_message_id,
                body=data.body,
                created_at=now,
            )
            db.add(message)
            await db.flush()
            if ai.active and ticket.support_mode == "ai" and ticket.owner_id == user.id:
                await queue_ai_reply(db, ticket_id, message.seq, limit=ai.queue_limit)
    return MessageView(
        id=message.id,
        seq=message.seq,
        author_kind="human",
        author_id=user.id,
        author_name=user.username,
        author_role=user.role.value,
        body=message.body,
        created_at=message.created_at,
    )


async def mark_read(
    db: AsyncSession, ticket_id: uuid.UUID, user: AuthenticatedUser, seq: int
) -> None:
    async with db.begin():
        ticket = await lock_ticket(db, ticket_id, user)
        if seq > ticket.last_message_seq:
            raise fail("validation_error", 422)
        position = await db.get(ReadPosition, (ticket_id, user.id))
        if position is None:
            db.add(ReadPosition(ticket_id=ticket_id, user_id=user.id, last_read_seq=seq))
        else:
            position.last_read_seq = max(position.last_read_seq, seq)


async def set_status(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: AuthenticatedUser,
    status: str,
    clock: Clock,
    *,
    ai_active: bool,
) -> TicketView:
    async with db.begin():
        ticket = await lock_ticket(db, ticket_id, user)
        hand_to_human(ticket)
        if ticket.status != status:
            ticket.status = status
            ticket.updated_at = clock.now()
            ticket.resolved_at = clock.now() if status == "resolved" else None
            ticket.resolved_by = user.id if status == "resolved" else None
    return await read_ticket(db, ticket_id, user, ai_active=ai_active)


async def handoff(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: AuthenticatedUser,
    clock: Clock,
    *,
    ai_active: bool,
) -> TicketView:
    async with db.begin():
        ticket = await lock_ticket(db, ticket_id, user)
        if ticket.support_mode != "human":
            hand_to_human(ticket)
            ticket.updated_at = clock.now()
    return await read_ticket(db, ticket_id, user, ai_active=ai_active)


def hand_to_human(ticket: Ticket) -> None:
    """The assistant stops answering; an unfinished generation is discarded on completion."""
    ticket.support_mode = "human"
    ticket.ai_state = "idle"
    ticket.ai_source_seq = None
    ticket.ai_started_at = None


async def queue_ai_reply(db: AsyncSession, ticket_id: uuid.UUID, seq: int, *, limit: int) -> None:
    """Point the assistant at message ``seq``; a full queue marks the ticket failed instead."""
    other = aliased(Ticket)
    busy = (
        select(func.count())
        .select_from(other)
        .where(other.ai_state.in_(ACTIVE_AI_STATES), other.support_mode == "ai")
        .scalar_subquery()
    )
    state: Any = case(
        (Ticket.ai_state.in_(ACTIVE_AI_STATES), Ticket.ai_state),
        (busy < limit, "pending"),
        else_="failed",
    )
    await db.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.support_mode == "ai")
        .values(ai_source_seq=seq, ai_state=state)
        .execution_options(synchronize_session=False)
    )


async def unread_count(db: AsyncSession, user: AuthenticatedUser) -> int:
    query = ticket_select(user).subquery()
    async with read_transaction(db):
        return await db.scalar(select(func.coalesce(func.sum(query.c.unread_count), 0))) or 0
