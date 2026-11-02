"""Ride commands of its participants: arrive, start, complete, cancel, release (ADR 0007).

One write transaction per command: lock the ride, decide with the rules of
``states.py`` (access, then a repeat, then the transition), move it with
``transitions.move_ride`` (status, stage time and history together) and run
the command's effects in the same transaction:

- cancel revokes a pending offer; an assigned driver is free again at once;
- release clears the driver and opens a new 180-second search, which runs
  its first step after the commit (the releasing driver is never asked again);
- complete calls the completion hook (payments, T08).

A repeat of an applied command returns the ride as it is, with no effect.
"""

import uuid
from datetime import datetime
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.modules.rides.completion import CompletionHook, on_ride_completed
from taxi_service.modules.rides.dispatch import (
    DispatchService,
    restart_search,
    revoke_pending_offers,
)
from taxi_service.modules.rides.exceptions import InvalidRideTransitionError, RideNotFoundError
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.policy import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from taxi_service.modules.rides.repository import RideRepository
from taxi_service.modules.rides.states import Actor, RideCommand, RideStatus, resolve_command
from taxi_service.modules.rides.transitions import move_ride
from taxi_service.modules.users.models import UserRole

_STAGE_TIME: Final = {
    RideCommand.ARRIVE: "arrived_at",
    RideCommand.START: "started_at",
    RideCommand.COMPLETE: "completed_at",
    RideCommand.CANCEL: "cancelled_at",
}


def actor_for(ride: Ride, user_id: uuid.UUID, role: UserRole) -> Actor:
    """The user's relation to this ride, from the row: its passenger, its driver or neither."""
    return Actor(
        role=role,
        is_ride_passenger=role is UserRole.PASSENGER and ride.passenger_id == user_id,
        is_assigned_driver=role is UserRole.DRIVER and ride.driver_id == user_id,
    )


class RideLifecycleService:
    """Commands on one ride; callers pass the user's id and role, the service checks access."""

    def __init__(
        self,
        session: AsyncSession,
        clock: Clock,
        policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
        on_completed: CompletionHook = on_ride_completed,
    ) -> None:
        self._session = session
        self._clock = clock
        self._policy = policy
        self._on_completed = on_completed
        self._rides = RideRepository(session)

    async def execute(
        self,
        ride_id: uuid.UUID,
        command: RideCommand,
        *,
        user_id: uuid.UUID,
        role: UserRole,
        reason: str | None = None,
    ) -> Ride:
        """Apply ``command`` and return the ride; 404/403/409 as ``states.resolve_command``.

        After a release the first search step runs in its own transaction
        (``_search_after_release``); the releasing driver gets only the
        release's own result, never what others changed afterwards.
        """
        async with self._session.begin():
            ride = await self._rides.lock_ride(ride_id)
            if ride is None:
                raise RideNotFoundError
            outcome = resolve_command(ride.status, command, actor_for(ride, user_id, role))
            if outcome.changed:
                await self._apply(ride, command, outcome.status, user_id, reason)
        if command is RideCommand.RELEASE:
            return await self._search_after_release(ride)
        return ride

    async def _search_after_release(self, released: Ride) -> Ride:
        """Run the first step of the new search; the answer for the releasing driver.

        The driver is no longer a participant (MVP_SPEC §3), so a cancel by the
        passenger or the next driver's accept that lands meanwhile stays
        hidden: the answer is the committed release (``searching``, no
        driver), or ``no_driver`` when this very search found nobody. A
        failing step is logged by ``start_search``; the loop continues it.
        """
        # Later reads must not overwrite the committed snapshot in the identity map.
        self._session.expunge(released)
        dispatch = DispatchService(self._session, self._clock, self._policy)
        after = await dispatch.start_search(released.id)
        same_search = after.search_started_at == released.search_started_at
        if after.status is RideStatus.NO_DRIVER and same_search:
            return after
        return released

    async def _apply(
        self,
        ride: Ride,
        command: RideCommand,
        target: RideStatus,
        user_id: uuid.UUID,
        reason: str | None,
    ) -> None:
        now = self._clock.now()
        current = ride.status
        moved = await move_ride(
            self._session,
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
            await revoke_pending_offers(self._session, ride.id, now)
        elif command is RideCommand.RELEASE:
            restart_search(ride, now, self._policy)
            await self._session.flush()
        elif command is RideCommand.COMPLETE:
            await self._on_completed(self._session, ride, now)


def _values(command: RideCommand, now: datetime, reason: str | None) -> dict[str, Any]:
    """Columns a command sets besides the status: its stage time, or what release clears."""
    if command is RideCommand.RELEASE:
        return {"driver_id": None, "assigned_at": None, "arrived_at": None}
    values: dict[str, Any] = {_STAGE_TIME[command]: now}
    if command is RideCommand.CANCEL:
        values["cancel_reason"] = reason
    return values
