import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import CurrentUser, require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.rides.dispatch_dependencies import DispatchServiceDep
from taxi_service.modules.rides.idempotency import REPLAYED_HEADER, IdempotencyKeyDep
from taxi_service.modules.rides.policy import DispatchPolicyDep
from taxi_service.modules.rides.schemas import (
    QuoteRequest,
    QuoteResponse,
    RideCreateRequest,
    RideResponse,
)
from taxi_service.modules.rides.service import RideService
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides", tags=["rides"])

PassengerUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.PASSENGER))]


def get_ride_service(
    session: SessionDep, clock: ClockDep, policy: DispatchPolicyDep
) -> RideService:
    return RideService(session, clock, policy)


RideServiceDep = Annotated[RideService, Depends(get_ride_service)]


@router.post(
    "/quotes", status_code=status.HTTP_201_CREATED, responses=error_responses(401, 403, 503)
)
async def create_quote(
    body: QuoteRequest, user: PassengerUser, rides: RideServiceDep, routing: RoutingProviderDep
) -> QuoteResponse:
    """Price a road route from `pickup` to `dropoff` (passenger only).

    The server builds the route with the external provider and prices it with
    the tariff `tariff_version`; the quote is valid for five minutes
    (`expires_at`) and is used by `POST /rides`. Sending a price is a 422.

    Errors: `422 validation_error`; `422 route_points_identical`; `422
    route_not_found`; `503 routing_unavailable`; `503 routing_provider_error`
    (`details.reason`). A failed route stores no quote.
    """
    return QuoteResponse.build(await rides.create_quote(user.id, body, routing))


@router.post("", status_code=status.HTTP_201_CREATED, responses=error_responses(401, 403, 404, 409))
async def create_ride(
    body: RideCreateRequest,
    user: PassengerUser,
    key: IdempotencyKeyDep,
    rides: RideServiceDep,
    dispatch: DispatchServiceDep,
    response: Response,
) -> RideResponse:
    """Order a ride from the passenger's own quote (passenger only).

    The ride starts in `searching` without a driver, with the route and the
    price copied from the quote; the price is never taken from the body.
    Header `Idempotency-Key` is required: repeating the same key with the
    same body returns the same ride (201, header `Idempotent-Replayed: true`)
    instead of a second one.

    Errors: `422 idempotency_key_required` / `idempotency_key_invalid`;
    `422 validation_error`; `404 quote_not_found` (unknown or another
    passenger's quote); `409 quote_expired` (five minutes passed);
    `409 quote_already_used`; `409 active_ride_exists`;
    `409 idempotency_key_reused` (same key, different body).

    The driver search starts right after the ride is stored: the nearest
    driver gets a 30-second offer, or the ride is already `no_driver` when
    nobody is available. A replay returns the current state and does not
    search again.
    """
    creation = await rides.create_ride(user.id, body, key)
    if creation.replayed:
        response.headers[REPLAYED_HEADER] = "true"
        return RideResponse.build(creation.ride)
    return RideResponse.build(await dispatch.start_search(creation.ride))


@router.get("/{ride_id}", responses=error_responses(401, 404))
async def read_ride(ride_id: uuid.UUID, user: CurrentUser, rides: RideServiceDep) -> RideResponse:
    """A ride with its status, driver (if assigned), route and fixed price.

    Visible to its passenger, the driver assigned to it and admins. Anyone
    else gets `404 ride_not_found`, as for an id that does not exist.
    """
    return RideResponse.build(
        await rides.get_ride(ride_id, viewer_id=user.id, viewer_role=user.role)
    )
