from fastapi import APIRouter

from taxi_service.modules.admin.router import router as admin_reads_router
from taxi_service.modules.auth.router import router as auth_router
from taxi_service.modules.drivers.admin_router import router as admin_drivers_router
from taxi_service.modules.drivers.router import router as drivers_router
from taxi_service.modules.geo.router import router as geo_router
from taxi_service.modules.payments.router import router as payments_router
from taxi_service.modules.rides.router import offers_router
from taxi_service.modules.rides.router import router as rides_router
from taxi_service.modules.users.router import router as users_router
from taxi_service.schemas.errors import error_responses

API_V1_PREFIX = "/api/v1"

# Declaring 422 here replaces FastAPI's default HTTPValidationError schema.
v1_router = APIRouter(prefix=API_V1_PREFIX, responses=error_responses(422, 500))
v1_router.include_router(auth_router)
v1_router.include_router(geo_router)
v1_router.include_router(users_router)
v1_router.include_router(drivers_router)
v1_router.include_router(admin_drivers_router)
v1_router.include_router(rides_router)
v1_router.include_router(payments_router)
v1_router.include_router(admin_reads_router)
v1_router.include_router(offers_router)
