from fastapi import APIRouter

from taxi_service.modules.auth.router import router as auth_router

API_V1_PREFIX = "/api/v1"

v1_router = APIRouter(prefix=API_V1_PREFIX)
v1_router.include_router(auth_router)
