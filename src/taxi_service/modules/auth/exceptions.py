"""Named authentication and authorization errors (rendered by the API error handler)."""

from taxi_service.core.errors import AppError


class NotAuthenticatedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=401, code="not_authenticated", message="Authentication required."
        )


class InvalidCredentialsError(AppError):
    """Same response for an unknown username and a wrong password."""

    def __init__(self) -> None:
        super().__init__(
            status_code=401, code="invalid_credentials", message="Invalid username or password."
        )


class ForbiddenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403, code="forbidden", message="This action is not allowed for your role."
        )


class CsrfFailedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            code="csrf_failed",
            message="Missing or invalid X-CSRF-Token header; get it from GET /api/v1/auth/session.",
        )


class OriginNotAllowedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403, code="origin_not_allowed", message="Request origin is not allowed."
        )


class TooManyLoginAttemptsError(AppError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            status_code=429,
            code="too_many_attempts",
            message="Too many login attempts; try again later.",
            details={"retry_after_seconds": retry_after_seconds},
        )
