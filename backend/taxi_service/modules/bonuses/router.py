from fastapi import APIRouter

from taxi_service.database.session import DbSession
from taxi_service.modules.bonuses import service
from taxi_service.modules.bonuses.schemas import BonusBalance
from taxi_service.modules.rides.dependencies import PassengerUser
from taxi_service.schemas.errors import error_responses

router = APIRouter(prefix="/bonuses", tags=["bonuses"])


@router.get("/me", responses=error_responses(401, 403))
async def mine(user: PassengerUser, db: DbSession) -> BonusBalance:
    return await service.my_balance(db, user.id)
