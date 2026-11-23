import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import AdminUser, CurrentUser
from taxi_service.modules.support import service
from taxi_service.modules.support.ai_config import SupportAIDep
from taxi_service.modules.support.schemas import (
    Category,
    CreateTicket,
    MarkRead,
    MessagePage,
    MessageView,
    SendMessage,
    SetStatus,
    TicketStatus,
    TicketView,
)
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(tags=["support"])


@router.post("/support/tickets", status_code=201)
async def create(
    body: CreateTicket,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    request: Request,
    ai: SupportAIDep,
) -> TicketView:
    return await service.create_ticket(
        db, user, body, clock=clock, limiter=request.app.state.support_ticket_limiter, ai=ai
    )


@router.get("/support/tickets")
async def mine(
    user: CurrentUser,
    db: DbSession,
    page: PageParamsDep,
    ai: SupportAIDep,
    status: TicketStatus | None = None,
) -> Page[TicketView]:
    return await service.list_tickets(
        db,
        user,
        status=status,
        category=None,
        query="",
        limit=page.limit,
        offset=page.offset,
        ai_active=ai.active,
    )


@router.get("/admin/support/tickets")
async def admin_tickets(
    user: AdminUser,
    db: DbSession,
    page: PageParamsDep,
    ai: SupportAIDep,
    status: TicketStatus | None = None,
    category: Category | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
) -> Page[TicketView]:
    return await service.list_tickets(
        db,
        user,
        status=status,
        category=category,
        query=q,
        limit=page.limit,
        offset=page.offset,
        ai_active=ai.active,
    )


@router.get("/support/unread")
async def unread(user: CurrentUser, db: DbSession) -> dict[str, int]:
    return {"count": await service.unread_count(db, user)}


@router.get("/support/tickets/{ticket_id}")
async def ticket(
    ticket_id: uuid.UUID, user: CurrentUser, db: DbSession, ai: SupportAIDep
) -> TicketView:
    return await service.read_ticket(db, ticket_id, user, ai_active=ai.active)


@router.get("/support/tickets/{ticket_id}/messages")
async def messages(
    ticket_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    after_seq: Annotated[int | None, Query(ge=0)] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> MessagePage:
    return await service.messages(
        db, ticket_id, user, after_seq=after_seq, before_seq=before_seq, limit=limit
    )


@router.post("/support/tickets/{ticket_id}/messages")
async def send(
    ticket_id: uuid.UUID,
    body: SendMessage,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    request: Request,
    ai: SupportAIDep,
) -> MessageView:
    return await service.send_message(
        db,
        ticket_id,
        user,
        body,
        clock=clock,
        limiter=request.app.state.support_message_limiter,
        ai=ai,
    )


@router.post("/support/tickets/{ticket_id}/read", status_code=204)
async def read(ticket_id: uuid.UUID, body: MarkRead, user: CurrentUser, db: DbSession) -> Response:
    await service.mark_read(db, ticket_id, user, body.last_read_seq)
    return Response(status_code=204)


@router.patch("/admin/support/tickets/{ticket_id}")
async def status(
    ticket_id: uuid.UUID,
    body: SetStatus,
    user: AdminUser,
    db: DbSession,
    clock: ClockDep,
    ai: SupportAIDep,
) -> TicketView:
    return await service.set_status(db, ticket_id, user, body.status, clock, ai_active=ai.active)


@router.post("/support/tickets/{ticket_id}/handoff")
async def handoff(
    ticket_id: uuid.UUID, user: CurrentUser, db: DbSession, clock: ClockDep, ai: SupportAIDep
) -> TicketView:
    return await service.handoff(db, ticket_id, user, clock, ai_active=ai.active)
