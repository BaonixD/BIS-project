"""Extension point run when a ride is completed: where T08 opens the payment record.

Contract (ADR 0007): ``complete`` calls the hook once, inside its own write
transaction, right after the ride became ``completed`` (``ride.status``,
``ride.completed_at`` and ``ride.amount_kzt`` are set) and the ride row is
locked. A repeated ``complete`` does not call it again. Whatever the hook
writes commits together with the completion; an exception rolls both back
and the ride stays ``in_progress``. The hook must not wait for external I/O.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import Ride

CompletionHook = Callable[[AsyncSession, Ride, datetime], Awaitable[None]]


async def on_ride_completed(session: AsyncSession, ride: Ride, now: datetime) -> None:
    """Nothing yet: payments (T08) add the unpaid payment record of ``ride`` here."""


def get_completion_hook(request: Request) -> CompletionHook:
    """FastAPI dependency: the hook set in ``create_app`` (tests may replace it)."""
    hook: CompletionHook = request.app.state.ride_completion_hook
    return hook


CompletionHookDep = Annotated[CompletionHook, Depends(get_completion_hook)]
