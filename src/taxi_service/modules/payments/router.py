import uuid

from fastapi import APIRouter

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.auth.dependencies import CurrentUser
from taxi_service.modules.payments import service
from taxi_service.modules.payments.dependencies import PaymentSettingsDep
from taxi_service.modules.payments.schemas import PaymentResponse
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/rides/{ride_id}/payment", tags=["payments"])


@router.get("", responses=error_responses(401, 404))
async def read_payment(
    ride_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: PaymentSettingsDep
) -> PaymentResponse:
    payment = await service.get_payment(db, ride_id, user_id=user.id, role=user.role)
    return PaymentResponse.build(payment, settings)


@router.post("/cash-received", responses=error_responses(401, 403, 404, 409))
async def receive_cash(
    ride_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    settings: PaymentSettingsDep,
) -> PaymentResponse:
    payment = await service.receive_cash(db, ride_id, user_id=user.id, role=user.role, clock=clock)
    return PaymentResponse.build(payment, settings)
