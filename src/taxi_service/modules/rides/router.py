from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.rides.idempotency import REPLAYED_HEADER, IdempotencyKeyDep
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


def get_ride_service(session: SessionDep, clock: ClockDep) -> RideService:
    return RideService(session, clock)


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
    """
    creation = await rides.create_ride(user.id, body, key)
    if creation.replayed:
        response.headers[REPLAYED_HEADER] = "true"
    return RideResponse.build(creation.ride)
