"""Ride commands of its participants, one write transaction each (ADR 0007)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.modules.payments.service import open_payment
from taxi_service.modules.rides import dispatch
from taxi_service.modules.rides.exceptions import InvalidRideTransitionError, RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.states import Actor, RideCommand, RideStatus, resolve_command
from taxi_service.modules.rides.transitions import lock_ride, move_ride
from taxi_service.modules.users.models import UserRole

# Runs inside the completion transaction with the ride locked; no external I/O.
CompletionHook = Callable[[AsyncSession, Ride, datetime], Awaitable[None]]

_STAGE_TIME: Final = {
    RideCommand.ARRIVE: "arrived_at",
    RideCommand.START: "started_at",
    RideCommand.COMPLETE: "completed_at",
    RideCommand.CANCEL: "cancelled_at",
}


async def on_ride_completed(db: AsyncSession, ride: Ride, now: datetime) -> None:
    await open_payment(db, ride, now)


def actor_for(ride: Ride, user_id: uuid.UUID, role: UserRole) -> Actor:
    return Actor(
        role=role,
        is_ride_passenger=role is UserRole.PASSENGER and ride.passenger_id == user_id,
        is_assigned_driver=role is UserRole.DRIVER and ride.driver_id == user_id,
    )


async def execute_command(
    db: AsyncSession,
    ride_id: uuid.UUID,
    command: RideCommand,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    reason: str | None = None,
    clock: Clock,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    on_completed: CompletionHook = on_ride_completed,
) -> Ride:
    """A repeat of an applied command returns the ride as it is, with no effect."""
    async with db.begin():
        ride = await lock_ride(db, ride_id)
        if ride is None:
            raise RideNotFoundError
        outcome = resolve_command(ride.status, command, actor_for(ride, user_id, role))
        if outcome.changed:
            now = clock.now()
            await _apply(db, ride, command, outcome.status, user_id, reason, now, policy)
            if command is RideCommand.COMPLETE:
                await on_completed(db, ride, now)
    if command is RideCommand.RELEASE:
        return await _search_after_release(db, ride, clock, policy)
    return ride


async def _search_after_release(
    db: AsyncSession, released: Ride, clock: Clock, policy: DispatchPolicy
) -> Ride:
    """The releaser is no longer a participant: only ``no_driver`` of this search is shown."""
    # Later reads must not overwrite the committed snapshot in the identity map.
    db.expunge(released)
    after = await dispatch.start_search(db, released.id, clock=clock, policy=policy)
    same_search = after.search_started_at == released.search_started_at
    if after.status is RideStatus.NO_DRIVER and same_search:
        return after
    return released


async def _apply(
    db: AsyncSession,
    ride: Ride,
    command: RideCommand,
    target: RideStatus,
    user_id: uuid.UUID,
    reason: str | None,
    now: datetime,
    policy: DispatchPolicy,
) -> None:
    current = ride.status
    moved = await move_ride(
        db,
        ride,
        command=command,
        to_status=target,
        now=now,
        actor_id=user_id,
        reason=reason,
        values=_values(command, now, reason),
    )
    if not moved:  # the ride row is locked: only a broken invariant gets here
        raise InvalidRideTransitionError(current_status=current.value, command=command.value)
    if command is RideCommand.CANCEL:
        await dispatch.revoke_pending_offers(db, ride.id, now)
    elif command is RideCommand.RELEASE:
        dispatch.restart_search(ride, now, policy)
        await db.flush()


def _values(command: RideCommand, now: datetime, reason: str | None) -> dict[str, Any]:
    if command is RideCommand.RELEASE:
        return {"driver_id": None, "assigned_at": None, "arrived_at": None}
    values: dict[str, Any] = {_STAGE_TIME[command]: now}
    if command is RideCommand.CANCEL:
        values["cancel_reason"] = reason
    return values
