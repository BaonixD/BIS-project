import uuid

from fastapi import APIRouter, Response, status

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.geo.dependencies import RoutingProviderDep
from taxi_service.modules.payments.dependencies import PaymentSettingsDep
from taxi_service.modules.rides import dispatch, history, lifecycle, service
from taxi_service.modules.rides.dependencies import (
    CompletionHookDep,
    DispatchPolicyDep,
    DriverUser,
    IdempotencyKeyDep,
    ParticipantUser,
    PassengerUser,
    RideFiltersDep,
)
from taxi_service.modules.rides.idempotency import REPLAYED_HEADER
from taxi_service.modules.rides.schemas import (
    CancelRequest,
    OfferResponse,
    QuoteRequest,
    QuoteResponse,
    ReleaseRequest,
    RideCreateRequest,
    RideDetailsResponse,
    RideResponse,
    RideSummary,
)
from taxi_service.modules.rides.states import RideCommand
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/rides", tags=["rides"])
offers_router = APIRouter(tags=["offers"])

COMMAND_ERRORS = error_responses(401, 403, 404, 409)


@router.post(
    "/quotes", status_code=status.HTTP_201_CREATED, responses=error_responses(401, 403, 503)
)
async def create_quote(
    body: QuoteRequest,
    user: PassengerUser,
    db: DbSession,
    clock: ClockDep,
    routing: RoutingProviderDep,
) -> QuoteResponse:
    quote = await service.create_quote(db, user.id, body, clock=clock, routing=routing)
    return QuoteResponse.build(quote)


@router.post(
    "", status_code=status.HTTP_201_CREATED, responses=error_responses(401, 403, 404, 409, 503)
)
async def create_ride(
    body: RideCreateRequest,
    user: PassengerUser,
    key: IdempotencyKeyDep,
    db: DbSession,
    clock: ClockDep,
    policy: DispatchPolicyDep,
    payments: PaymentSettingsDep,
    response: Response,
) -> RideResponse:
    creation = await service.order_ride(
        db, user.id, body, key, clock=clock, policy=policy, kaspi_enabled=payments.kaspi_enabled
    )
    if creation.replayed:
        response.headers[REPLAYED_HEADER] = "true"
    return RideResponse.build(creation.ride)


@router.get("", responses=error_responses(401, 403))
async def list_my_rides(
    user: ParticipantUser, db: DbSession, page: PageParamsDep, filters: RideFiltersDep
) -> Page[RideSummary]:
    result = await history.list_history(
        db, user.id, user.role, filters, limit=page.limit, offset=page.offset
    )
    return RideSummary.page(result, page)


@router.get("/{ride_id}", responses=error_responses(401, 404))
async def read_ride(ride_id: uuid.UUID, user: CurrentUser, db: DbSession) -> RideDetailsResponse:
    details = await service.get_ride(db, ride_id, viewer_id=user.id, viewer_role=user.role)
    return RideDetailsResponse.with_driver(details.ride, details.driver)


@router.post("/{ride_id}/arrive", responses=COMMAND_ERRORS)
async def arrive(
    ride_id: uuid.UUID, user: CurrentUser, db: DbSession, clock: ClockDep
) -> RideResponse:
    ride = await lifecycle.execute_command(
        db, ride_id, RideCommand.ARRIVE, user_id=user.id, role=user.role, clock=clock
    )
    return RideResponse.build(ride)


@router.post("/{ride_id}/start", responses=COMMAND_ERRORS)
async def start(
    ride_id: uuid.UUID, user: CurrentUser, db: DbSession, clock: ClockDep
) -> RideResponse:
    ride = await lifecycle.execute_command(
        db, ride_id, RideCommand.START, user_id=user.id, role=user.role, clock=clock
    )
    return RideResponse.build(ride)


@router.post("/{ride_id}/complete", responses=COMMAND_ERRORS)
async def complete(
    ride_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    on_completed: CompletionHookDep,
) -> RideResponse:
    ride = await lifecycle.execute_command(
        db,
        ride_id,
        RideCommand.COMPLETE,
        user_id=user.id,
        role=user.role,
        clock=clock,
        on_completed=on_completed,
    )
    return RideResponse.build(ride)


@router.post("/{ride_id}/cancel", responses=COMMAND_ERRORS)
async def cancel(
    ride_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    body: CancelRequest | None = None,
) -> RideResponse:
    ride = await lifecycle.execute_command(
        db,
        ride_id,
        RideCommand.CANCEL,
        user_id=user.id,
        role=user.role,
        reason=body.reason if body is not None else None,
        clock=clock,
    )
    return RideResponse.build(ride)


@router.post("/{ride_id}/release", responses=COMMAND_ERRORS)
async def release(
    ride_id: uuid.UUID,
    body: ReleaseRequest,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    policy: DispatchPolicyDep,
) -> RideResponse:
    ride = await lifecycle.execute_command(
        db,
        ride_id,
        RideCommand.RELEASE,
        user_id=user.id,
        role=user.role,
        reason=body.reason,
        clock=clock,
        policy=policy,
    )
    return RideResponse.build(ride)


@offers_router.get("/drivers/me/offers", responses=error_responses(401, 403))
async def list_my_offers(
    user: DriverUser, db: DbSession, clock: ClockDep, page: PageParamsDep
) -> Page[OfferResponse]:
    result = await dispatch.list_pending_offers(
        db, user.id, clock=clock, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[OfferResponse.build(offer, ride) for offer, ride in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@offers_router.post("/ride-offers/{offer_id}/accept", responses=error_responses(401, 403, 404, 409))
async def accept_offer(
    offer_id: uuid.UUID, user: DriverUser, db: DbSession, clock: ClockDep, policy: DispatchPolicyDep
) -> RideResponse:
    ride = await dispatch.accept_offer(db, offer_id, user.id, clock=clock, policy=policy)
    return RideResponse.build(ride)


@offers_router.post("/ride-offers/{offer_id}/reject", responses=error_responses(401, 403, 404, 409))
async def reject_offer(
    offer_id: uuid.UUID, user: DriverUser, db: DbSession, clock: ClockDep, policy: DispatchPolicyDep
) -> OfferResponse:
    offer, ride = await dispatch.reject_offer(db, offer_id, user.id, clock=clock, policy=policy)
    return OfferResponse.build(offer, ride)
