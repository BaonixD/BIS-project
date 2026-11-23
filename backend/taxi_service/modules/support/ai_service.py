"""Steps of one assistant reply; each is a short transaction, the model call happens between them.

A ticket's ``ai_source_seq`` names the user message to answer. Every completion is checked
against the number it was claimed with, so a stale result never overwrites newer state.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from sqlalchemy import ColumnElement, Row, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.support.ai_client import Turn
from taxi_service.modules.support.ai_knowledge import ticket_context, with_subject
from taxi_service.modules.support.models import Message, Ticket
from taxi_service.modules.users.models import User, UserRole

HISTORY_MESSAGES: Final = 12
HISTORY_CHARS: Final = 12_000

Outcome = Literal["published", "failed", "superseded", "dropped"]


@dataclass(frozen=True, slots=True)
class Claim:
    ticket_id: uuid.UUID
    source_seq: int


@dataclass(frozen=True, slots=True)
class Context:
    system: str
    turns: list[Turn]


def _rowcount(result: object) -> int:
    return result.rowcount if isinstance(result, CursorResult) else 0


async def recover_interrupted(db: AsyncSession) -> int:
    """A reply cut off by a restart may or may not have reached Gemini: mark it failed."""
    async with db.begin():
        result = await db.execute(
            update(Ticket)
            .where(Ticket.ai_state == "running")
            .values(ai_state="failed", ai_started_at=None)
        )
    return _rowcount(result)


async def claim_next(db: AsyncSession, clock: Clock) -> Claim | None:
    async with db.begin():
        row = (
            await db.execute(
                select(Ticket.id, Ticket.ai_source_seq)
                .where(
                    Ticket.ai_state == "pending",
                    Ticket.support_mode == "ai",
                    Ticket.ai_source_seq.is_not(None),
                )
                .order_by(Ticket.updated_at, Ticket.id)
                .limit(1)
            )
        ).one_or_none()
        if row is None or row.ai_source_seq is None:
            return None
        result = await db.execute(
            update(Ticket)
            .where(
                Ticket.id == row.id,
                Ticket.ai_state == "pending",
                Ticket.ai_source_seq == row.ai_source_seq,
            )
            .values(ai_state="running", ai_started_at=clock.now())
        )
    return Claim(row.id, row.ai_source_seq) if _rowcount(result) == 1 else None


async def load_context(db: AsyncSession, claim: Claim, prompt: str) -> Context | None:
    async with read_transaction(db):
        ticket = (
            await db.execute(
                select(Ticket.owner_id, Ticket.category, Ticket.subject, Ticket.ride_id, User.role)
                .join(User, User.id == Ticket.owner_id)
                .where(Ticket.id == claim.ticket_id)
            )
        ).one_or_none()
        if ticket is None:
            return None
        rows = (
            await db.execute(
                select(Message.seq, Message.author_kind, Message.author_id, Message.body)
                .where(Message.ticket_id == claim.ticket_id, Message.seq <= claim.source_seq)
                .order_by(Message.seq.desc())
                .limit(HISTORY_MESSAGES)
            )
        ).all()
    turns = conversation(rows, owner_id=ticket.owner_id, subject=ticket.subject)
    if not turns or turns[-1].role != "user":
        return None
    system = ticket_context(
        prompt,
        UserRole(ticket.role),
        ticket.category,
        linked_ride=ticket.ride_id is not None,
        question=rows[0].body,
    )
    return Context(system=system, turns=turns)


def conversation(
    rows_newest_first: Sequence[Row[int, str, uuid.UUID | None, str]],
    *,
    owner_id: uuid.UUID,
    subject: str,
) -> list[Turn]:
    """The latest messages within the budget; the newest one is always kept whole."""
    picked: list[Turn] = []
    total = 0
    for seq, kind, author_id, body in rows_newest_first:
        if kind == "assistant":
            role: Literal["user", "model"] = "model"
        elif author_id == owner_id:
            role = "user"
        else:
            continue
        text = with_subject(subject, body) if seq == 1 else body
        if picked and total + len(text) > HISTORY_CHARS:
            break
        picked.append(Turn(role, text))
        total += len(text)
    picked.reverse()
    while picked and picked[0].role == "model":
        picked.pop(0)
    merged: list[Turn] = []
    for turn in picked:
        if merged and merged[-1].role == turn.role:
            merged[-1] = Turn(turn.role, f"{merged[-1].text}\n\n{turn.text}")
        else:
            merged.append(turn)
    return merged


async def publish_reply(db: AsyncSession, claim: Claim, text: str, clock: Clock) -> Outcome:
    async with db.begin():
        now = clock.now()
        seq = await db.scalar(
            update(Ticket)
            .where(*_still_current(claim))
            .values(
                last_message_seq=Ticket.last_message_seq + 1,
                ai_state="idle",
                ai_source_seq=None,
                ai_started_at=None,
                updated_at=now,
            )
            .returning(Ticket.last_message_seq)
        )
        if seq is None:
            return await _requeue_newer(db, claim)
        db.add(
            Message(
                ticket_id=claim.ticket_id,
                seq=seq,
                author_kind="assistant",
                author_id=None,
                ai_reply_to_seq=claim.source_seq,
                client_message_id=uuid.uuid4(),
                body=text,
                created_at=now,
            )
        )
    return "published"


async def fail_reply(db: AsyncSession, claim: Claim) -> Outcome:
    async with db.begin():
        result = await db.execute(
            update(Ticket)
            .where(*_still_current(claim))
            .values(ai_state="failed", ai_started_at=None)
        )
        if _rowcount(result) == 1:
            return "failed"
        return await _requeue_newer(db, claim)


def _still_current(claim: Claim) -> tuple[ColumnElement[bool], ...]:
    return (
        Ticket.id == claim.ticket_id,
        Ticket.support_mode == "ai",
        Ticket.ai_state == "running",
        Ticket.ai_source_seq == claim.source_seq,
        Ticket.status != "resolved",
    )


async def _requeue_newer(db: AsyncSession, claim: Claim) -> Outcome:
    """A message arrived during generation: answer it next instead of the old one."""
    result = await db.execute(
        update(Ticket)
        .where(
            Ticket.id == claim.ticket_id,
            Ticket.support_mode == "ai",
            Ticket.ai_state == "running",
            Ticket.ai_source_seq != claim.source_seq,
        )
        .values(ai_state="pending", ai_started_at=None)
    )
    return "superseded" if _rowcount(result) == 1 else "dropped"
