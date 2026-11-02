from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taxi_service.api.exception_handlers import register_exception_handlers
from taxi_service.api.router import api_router
from taxi_service.core.clock import Clock, SystemClock
from taxi_service.core.config import Settings
from taxi_service.core.lifespan import lifespan
from taxi_service.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from taxi_service.modules.auth.dependencies import CSRF_HEADER_NAME
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.auth.rate_limit import LoginAttemptLimiter


API_DESCRIPTION = """\
Backend MVP of a taxi service in Almaty (KZT).

**Session in Swagger UI** (the browser keeps the HttpOnly cookie itself):

1. `POST /api/v1/auth/register`, then `POST /api/v1/auth/login`.
2. `GET /api/v1/auth/session` and copy `csrf_token`.
3. **Authorize** -> `CsrfToken`: paste the token. It is sent as `X-CSRF-Token`,
   required on every POST/PUT/PATCH/DELETE made with the session.
4. `POST /api/v1/auth/logout` ends the session; its CSRF token stops working.

Errors always use the `ErrorResponse` envelope.
"""


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    app = FastAPI(
        title="Mini Taxi Service",
        version="0.1.0",
        description=API_DESCRIPTION,
        lifespan=lifespan,
    )
    settings = settings or Settings()
    clock = clock or SystemClock()
    app.state.settings = settings
    app.state.clock = clock
    app.state.password_hasher = PasswordHasher.from_settings(settings)
    app.state.login_limiter = LoginAttemptLimiter.from_settings(settings, clock)
    # Added first, so RequestIdMiddleware wraps it: preflight answers get an ID too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER_NAME, REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
