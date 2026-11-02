from fastapi import APIRouter

from taxi_service.modules.auth.router import router as auth_router
from taxi_service.schemas.errors import error_responses

API_V1_PREFIX = "/api/v1"

# Declaring 422 here replaces FastAPI's default HTTPValidationError schema.
v1_router = APIRouter(prefix=API_V1_PREFIX, responses=error_responses(422, 500))
v1_router.include_router(auth_router)
