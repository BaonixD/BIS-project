from fastapi import APIRouter

from taxi_service.api import health
from taxi_service.api.v1 import v1_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(v1_router)
