import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.rides.completion import CompletionHookDep
from taxi_service.modules.rides.lifecycle import RideLifecycleService
from taxi_service.modules.rides.policy import DispatchPolicyDep
from taxi_service.modules.rides.schemas import CancelRequest, ReleaseRequest, RideResponse
from taxi_service.modules.rides.states import RideCommand
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides", tags=["rides"])

COMMAND_ERRORS = error_responses(401, 403, 404, 409)


def get_lifecycle_service(
    session: SessionDep, clock: ClockDep, policy: DispatchPolicyDep, hook: CompletionHookDep
) -> RideLifecycleService:
    return RideLifecycleService(session, clock, policy, on_completed=hook)


LifecycleDep = Annotated[RideLifecycleService, Depends(get_lifecycle_service)]


async def _run(
    lifecycle: RideLifecycleService,
    ride_id: uuid.UUID,
    command: RideCommand,
    user: CurrentUser,
    reason: str | None = None,
) -> RideResponse:
    ride = await lifecycle.execute(ride_id, command, user_id=user.id, role=user.role, reason=reason)
    return RideResponse.build(ride)


@router.post("/{ride_id}/arrive", responses=COMMAND_ERRORS)
async def arrive(ride_id: uuid.UUID, user: CurrentUser, lifecycle: LifecycleDep) -> RideResponse:
    """The assigned driver is at the pickup: `assigned` -> `arrived`.

    Errors: `404 ride_not_found` (unknown or not your ride);
    `403 ride_command_forbidden` (not your command, admin included);
    `409 invalid_ride_transition` (`details.current_status`). Repeating an
    applied command returns the ride unchanged.
    """
    return await _run(lifecycle, ride_id, RideCommand.ARRIVE, user)


@router.post("/{ride_id}/start", responses=COMMAND_ERRORS)
async def start(ride_id: uuid.UUID, user: CurrentUser, lifecycle: LifecycleDep) -> RideResponse:
    """The assigned driver starts the trip: `arrived` -> `in_progress` (no cancel after).

    Errors: `404 ride_not_found` (unknown or not your ride);
    `403 ride_command_forbidden` (not your command, admin included);
    `409 invalid_ride_transition` (`details.current_status`). Repeating an
    applied command returns the ride unchanged.
    """
    return await _run(lifecycle, ride_id, RideCommand.START, user)


@router.post("/{ride_id}/complete", responses=COMMAND_ERRORS)
async def complete(ride_id: uuid.UUID, user: CurrentUser, lifecycle: LifecycleDep) -> RideResponse:
    """The assigned driver ends the trip: `in_progress` -> `completed`; the driver is free.

    Errors: `404 ride_not_found` (unknown or not your ride);
    `403 ride_command_forbidden` (not your command, admin included);
    `409 invalid_ride_transition` (`details.current_status`). Repeating an
    applied command returns the ride unchanged.
    """
    return await _run(lifecycle, ride_id, RideCommand.COMPLETE, user)


@router.post("/{ride_id}/cancel", responses=COMMAND_ERRORS)
async def cancel(
    ride_id: uuid.UUID,
    user: CurrentUser,
    lifecycle: LifecycleDep,
    body: CancelRequest | None = None,
) -> RideResponse:
    """The passenger cancels before the trip starts (`searching`, `assigned`, `arrived`).

    The body is optional (`reason`). A pending driver offer is revoked; an
    assigned driver is free for other rides at once.

    Errors: `404 ride_not_found` (unknown or not your ride);
    `403 ride_command_forbidden` (not your command, admin included);
    `409 invalid_ride_transition` (`details.current_status`). Repeating an
    applied command returns the ride unchanged.
    """
    reason = body.reason if body is not None else None
    return await _run(lifecycle, ride_id, RideCommand.CANCEL, user, reason)


@router.post("/{ride_id}/release", responses=COMMAND_ERRORS)
async def release(
    ride_id: uuid.UUID, body: ReleaseRequest, user: CurrentUser, lifecycle: LifecycleDep
) -> RideResponse:
    """The assigned driver gives the ride up before the start, with a `reason`.

    The ride returns to `searching` without a driver and a new 180-second
    search begins at once; this driver is not asked for this ride again. The
    response shows the ride after the first search step (`searching` or
    `no_driver`); the ride is no longer visible to this driver afterwards.

    Errors: `404 ride_not_found` (unknown or not your ride);
    `403 ride_command_forbidden` (not your command, admin included);
    `409 invalid_ride_transition` (`details.current_status`). Repeating an
    applied command returns the ride unchanged.
    """
    return await _run(lifecycle, ride_id, RideCommand.RELEASE, user, body.reason)
