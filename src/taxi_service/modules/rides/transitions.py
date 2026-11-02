"""The one way a ride's status changes: a conditional UPDATE and its ``ride_events`` row.

Dispatch (assign, mark_no_driver) and the ride commands (arrive, start,
complete, cancel, release) all call :func:`move_ride` inside their write
transaction, after locking the ride, so status and history never disagree.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import Ride, RideEvent
from taxi_service.modules.rides.states import RideCommand, RideStatus


async def move_ride(
    session: AsyncSession,
    ride: Ride,
    *,
    command: RideCommand,
    to_status: RideStatus,
    now: datetime,
    actor_id: uuid.UUID | None,
    reason: str | None = None,
    values: Mapping[str, Any] | None = None,
) -> bool:
    """``ride.status`` -> ``to_status`` plus column ``values``; ``False`` if it moved meanwhile.

    The UPDATE matches the status the caller saw; on success one event
    ``(from, to, command, actor_id, reason, now)`` is added and ``ride`` is
    refreshed. ``actor_id`` is ``None`` for the dispatch loop.
    """
    from_status = ride.status
    statement = (
        update(Ride)
        .where(Ride.id == ride.id, Ride.status == from_status)
        .values(status=to_status, updated_at=now, **(values or {}))
    )
    result = await session.execute(statement, execution_options={"synchronize_session": False})
    if cast(CursorResult[Any], result).rowcount != 1:
        return False
    session.add(
        RideEvent(
            id=uuid.uuid4(),
            ride_id=ride.id,
            from_status=from_status,
            to_status=to_status,
            command=command,
            actor_id=actor_id,
            reason=reason,
            created_at=now,
        )
    )
    await session.flush()
    await session.refresh(ride)
    return True
