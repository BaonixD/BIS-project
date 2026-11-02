from typing import Literal

from taxi_service.core.errors import AppError

ProviderFailure = Literal[
    "timeout",
    "connection_error",
    "rate_limited",
    "provider_unavailable",
    "rejected",
    "invalid_response",
]


class RoutingUnavailableError(AppError):
    """Road routing is not configured, so no provider request is attempted."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="routing_unavailable",
            message="Road routing is not configured.",
        )


class RoutingProviderError(AppError):
    """The provider failed, refused the request or returned an unusable route."""

    def __init__(self, reason: ProviderFailure, *, provider_status: int | None = None) -> None:
        super().__init__(
            status_code=503,
            code="routing_provider_error",
            message="Road routing provider is temporarily unavailable.",
            details={"reason": reason, "provider_status": provider_status},
        )
        self.reason = reason


class RoutePointsIdenticalError(AppError):
    """Origin and destination are the same point; the provider is not asked."""

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="route_points_identical",
            message="Origin and destination must be different points.",
        )


class RouteNotFoundError(AppError):
    """The provider found no drivable road route between the points."""

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="route_not_found",
            message="No road route was found between the given points.",
        )
