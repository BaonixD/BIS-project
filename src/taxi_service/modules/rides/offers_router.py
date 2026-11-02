import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from taxi_service.modules.auth.dependencies import require_roles
from taxi_service.modules.auth.service import AuthenticatedUser
from taxi_service.modules.rides.dispatch_dependencies import DispatchServiceDep
from taxi_service.modules.rides.offer_schemas import OfferResponse
from taxi_service.modules.rides.schemas import RideResponse
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(tags=["offers"])

DriverUser = Annotated[AuthenticatedUser, Depends(require_roles(UserRole.DRIVER))]


@router.get("/drivers/me/offers", responses=error_responses(401, 403))
async def list_my_offers(
    user: DriverUser, dispatch: DispatchServiceDep, page: PageParamsDep
) -> Page[OfferResponse]:
    """The driver's pending offers that can still be accepted (at most one), newest first.

    Each offer shows the ride's pickup, dropoff, road distance and duration,
    the fixed price and `expires_at`: 30 seconds after it was made. Poll this
    list; an offer disappears when it is answered, expires or is revoked.
    """
    result = await dispatch.pending_offers(user.id, limit=page.limit, offset=page.offset)
    return Page(
        items=[OfferResponse.build(offer, ride) for offer, ride in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@router.post("/ride-offers/{offer_id}/accept", responses=error_responses(401, 403, 404, 409))
async def accept_offer(
    offer_id: uuid.UUID, user: DriverUser, dispatch: DispatchServiceDep
) -> RideResponse:
    """Accept the offer: the ride becomes `assigned` to this driver.

    Accepting an offer you already accepted returns the ride again.

    Errors: `404 offer_not_found` (unknown or another driver's offer);
    `409 offer_expired` (`now >= expires_at`; the ride goes to the next
    driver); `409 invalid_offer_transition` (rejected or revoked);
    `409 driver_busy` (you already have an active ride).
    """
    return RideResponse.build(await dispatch.accept_offer(offer_id, user.id))


@router.post("/ride-offers/{offer_id}/reject", responses=error_responses(401, 403, 404, 409))
async def reject_offer(
    offer_id: uuid.UUID, user: DriverUser, dispatch: DispatchServiceDep
) -> OfferResponse:
    """Decline the offer; the ride is offered to the next nearest driver at once.

    Rejecting again returns the rejected offer. Errors: `404 offer_not_found`;
    `409 offer_expired`; `409 invalid_offer_transition` (already accepted or
    revoked).
    """
    offer, ride = await dispatch.reject_offer(offer_id, user.id)
    return OfferResponse.build(offer, ride)
