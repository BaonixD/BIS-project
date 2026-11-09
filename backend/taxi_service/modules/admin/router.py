import uuid
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Query

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import DbSession
from taxi_service.modules.admin import service
from taxi_service.modules.admin.schemas import (
    AccountAccessUpdate,
    AdminOverview,
    AdminRideSummary,
    AdminUserResponse,
)
from taxi_service.modules.auth.dependencies import AdminUser
from taxi_service.modules.payments.models import PaymentMethod, PaymentStatus
from taxi_service.modules.rides import history
from taxi_service.modules.rides.dependencies import RideFiltersDep
from taxi_service.modules.rides.schemas import RideSummary
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.users import service as users_service
from taxi_service.modules.users.models import UserRole
from taxi_service.schemas.errors import error_responses
from taxi_service.schemas.pagination import Page, PageParamsDep

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/rides", responses=error_responses(401, 403))
async def list_all_rides(
    _admin: AdminUser,
    db: DbSession,
    page: PageParamsDep,
    filters: RideFiltersDep,
    passenger_id: Annotated[uuid.UUID | None, Query(description="Only this passenger.")] = None,
    driver_id: Annotated[
        uuid.UUID | None, Query(description="Only rides assigned to this driver now.")
    ] = None,
    q: Annotated[str, Query(max_length=100)] = "",
    payment_status: PaymentStatus | None = None,
    payment_method: PaymentMethod | None = None,
    tariff: Tariff | None = None,
) -> Page[AdminRideSummary]:
    result = await history.list_all_rides(
        db,
        replace(
            filters,
            query=q,
            payment_status=payment_status,
            payment_method=payment_method,
            tariff=tariff,
        ),
        passenger_id=passenger_id,
        driver_id=driver_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[
            AdminRideSummary(
                **RideSummary.build(row).model_dump(),
                passenger_name=row.passenger_name or "Пассажир",
                driver_name=row.driver_name,
            )
            for row in result.rows
        ],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@router.get("/users", responses=error_responses(401, 403))
async def list_users(
    _admin: AdminUser,
    db: DbSession,
    page: PageParamsDep,
    role: Annotated[UserRole | None, Query(description="Only accounts with this role.")] = None,
    q: Annotated[str, Query(max_length=100)] = "",
    blocked: bool | None = None,
) -> Page[AdminUserResponse]:
    result = await users_service.list_users(
        db, role, limit=page.limit, offset=page.offset, query=q, blocked=blocked
    )
    return Page(
        items=[AdminUserResponse.model_validate(row) for row in result.rows],
        limit=page.limit,
        offset=page.offset,
        total=result.total,
    )


@router.get("/overview", responses=error_responses(401, 403))
async def read_overview(_admin: AdminUser, db: DbSession) -> AdminOverview:
    return await service.overview(db)


@router.get("/users/{user_id}", responses=error_responses(401, 403, 404))
async def read_user(user_id: uuid.UUID, _admin: AdminUser, db: DbSession) -> AdminUserResponse:
    return AdminUserResponse.model_validate(await service.read_user(db, user_id))


@router.put("/users/{user_id}/access", responses=error_responses(401, 403, 404, 409))
async def update_access(
    user_id: uuid.UUID, body: AccountAccessUpdate, admin: AdminUser, db: DbSession, clock: ClockDep
) -> AdminUserResponse:
    await service.set_account_access(db, user_id, admin.id, body, clock=clock)
    return AdminUserResponse.model_validate(await service.read_user(db, user_id))
