import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.modules.rides.models import Ride, RideEvent
from taxi_service.modules.rides.states import RideCommand, RideStatus


async def lock_ride(db: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    """Fresh and locked; lock the ride before its offers or payment (ADR 0006)."""
    result = await db.execute(
        select(Ride)
        .where(Ride.id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def move_ride(
    db: AsyncSession,
    ride: Ride,
    *,
    command: RideCommand,
    to_status: RideStatus,
    now: datetime,
    actor_id: uuid.UUID | None,
    reason: str | None = None,
    values: Mapping[str, Any] | None = None,
) -> bool:
    """The only status change: UPDATE plus its event; ``False`` if the ride moved meanwhile."""
    from_status = ride.status
    statement = (
        update(Ride)
        .where(Ride.id == ride.id, Ride.status == from_status)
        .values(status=to_status, updated_at=now, **(values or {}))
    )
    result = await db.execute(statement, execution_options={"synchronize_session": False})
    if cast(CursorResult[Any], result).rowcount != 1:
        return False
    db.add(
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
    await db.flush()
    await db.refresh(ride)
    return True
