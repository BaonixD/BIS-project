import uuid

from fastapi import APIRouter

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.payments import service
from taxi_service.modules.payments.dependencies import PaymentSettingsDep
from taxi_service.modules.payments.schemas import (
    PaymentCommandResponse,
    PaymentConfirmRequest,
    PaymentMethodRequest,
    PaymentReportRequest,
    PaymentResponse,
)
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides/{ride_id}/payment", tags=["payments"])

COMMAND_ERRORS = error_responses(401, 403, 404, 409)


@router.get("", responses=error_responses(401, 404, 409))
async def read_payment(
    ride_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: PaymentSettingsDep
) -> PaymentResponse:
    payment = await service.get_payment(db, ride_id, user_id=user.id, role=user.role)
    return PaymentResponse.build(payment, settings, viewer_role=user.role)


@router.put("/method", responses=error_responses(401, 403, 404, 409, 503))
async def change_payment_method(
    ride_id: uuid.UUID,
    body: PaymentMethodRequest,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    settings: PaymentSettingsDep,
) -> PaymentCommandResponse:
    result = await service.change_method(
        db, ride_id, body.method, user_id=user.id, role=user.role, clock=clock, settings=settings
    )
    return PaymentCommandResponse.after(
        result.payment, settings, changed=result.changed, viewer_role=user.role
    )


@router.post("/report", responses=COMMAND_ERRORS)
async def report_payment(
    ride_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    settings: PaymentSettingsDep,
    body: PaymentReportRequest | None = None,
) -> PaymentCommandResponse:
    result = await service.report_payment(db, ride_id, user_id=user.id, role=user.role, clock=clock)
    return PaymentCommandResponse.after(
        result.payment, settings, changed=result.changed, viewer_role=user.role
    )


@router.post("/confirm", responses=COMMAND_ERRORS)
async def confirm_payment(
    ride_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    settings: PaymentSettingsDep,
    body: PaymentConfirmRequest | None = None,
) -> PaymentCommandResponse:
    result = await service.confirm_payment(
        db,
        ride_id,
        body.reference if body is not None else None,
        user_id=user.id,
        role=user.role,
        clock=clock,
    )
    return PaymentCommandResponse.after(
        result.payment, settings, changed=result.changed, viewer_role=user.role
    )
