from fastapi import APIRouter

from taxi_service.api import health

api_router = APIRouter()
api_router.include_router(health.router)
