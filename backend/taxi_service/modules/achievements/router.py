from fastapi import APIRouter

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.achievements import service
from taxi_service.modules.achievements.schemas import Progress
from taxi_service.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["achievements"])


@router.get("/users/me/achievements")
async def progress(user: CurrentUser, db: DbSession, clock: ClockDep) -> Progress:
    return await service.progress(db, user.id, user.role, clock.now())
