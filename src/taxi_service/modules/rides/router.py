from typing import Annotated

from fastapi import APIRouter, Depends, status

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.rides.schemas import QuoteRequest, QuoteResponse
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
