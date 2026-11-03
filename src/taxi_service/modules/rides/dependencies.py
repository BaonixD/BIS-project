from typing import Annotated

from fastapi import Depends, Header, Query, Request
from pydantic import AwareDatetime

from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.exceptions import InvalidDateRangeError
from taxi_service.modules.rides.history import RideFilters
from taxi_service.modules.rides.idempotency import IDEMPOTENCY_HEADER, parse_idempotency_key
from taxi_service.modules.rides.lifecycle import CompletionHook
from taxi_service.modules.rides.policy import DispatchPolicy
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.users.models import UserRole

PassengerUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.PASSENGER))]
DriverUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.DRIVER))]
ParticipantUser = Annotated[
    AuthenticatedUser, Depends(require_roles(UserRole.PASSENGER, UserRole.DRIVER))
]


def get_dispatch_policy(request: Request) -> DispatchPolicy:
    policy: DispatchPolicy = request.app.state.dispatch_policy
    return policy


DispatchPolicyDep = Annotated[DispatchPolicy, Depends(get_dispatch_policy)]


def get_completion_hook(request: Request) -> CompletionHook:
    hook: CompletionHook = request.app.state.ride_completion_hook
    return hook


CompletionHookDep = Annotated[CompletionHook, Depends(get_completion_hook)]


def get_idempotency_key(
    key: Annotated[
        str | None,
        Header(
            alias=IDEMPOTENCY_HEADER,
            description="Required. 1-128 visible ASCII characters, unique per new order "
            "(a UUID is a good choice). Repeat it to retry the same request safely.",
        ),
    ] = None,
) -> str:
    return parse_idempotency_key(key)


IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]


def ride_filters(
    status: Annotated[
        list[RideStatus] | None,
        Query(description="Only rides in these statuses; repeat the parameter for several."),
    ] = None,
    created_from: Annotated[
        AwareDatetime | None,
        Query(description="Created at or after this time (inclusive); ISO 8601 with offset."),
    ] = None,
    created_to: Annotated[
        AwareDatetime | None,
        Query(description="Created before this time (exclusive); ISO 8601 with offset."),
    ] = None,
) -> RideFilters:
    if created_from is not None and created_to is not None and created_from > created_to:
        raise InvalidDateRangeError
    return RideFilters(
        statuses=frozenset(status or ()), created_from=created_from, created_to=created_to
    )


RideFiltersDep = Annotated[RideFilters, Depends(ride_filters)]
