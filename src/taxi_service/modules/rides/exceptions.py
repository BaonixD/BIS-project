from taxi_service.core.errors import AppError


class RideNotFoundError(AppError):
    """The ride does not exist or belongs to someone else; both look the same."""

    def __init__(self) -> None:
        super().__init__(status_code=404, code="ride_not_found", message="Ride not found.")


class RideCommandForbiddenError(AppError):
    """A participant (or admin) may see the ride but may not issue this command."""

    def __init__(self, *, command: str) -> None:
        super().__init__(
            status_code=403,
            code="ride_command_forbidden",
            message="This ride command is not allowed for the current user.",
            details={"command": command},
        )


class InvalidRideTransitionError(AppError):
    """The command does not apply to the ride's current status."""

    def __init__(self, *, current_status: str, command: str) -> None:
        super().__init__(
            status_code=409,
            code="invalid_ride_transition",
            message="The ride command is not allowed in the current ride status.",
            details={"current_status": current_status, "command": command},
        )


class InvalidOfferTransitionError(AppError):
    """The offer was already decided; only a pending offer changes status."""

    def __init__(self, *, current_status: str, command: str) -> None:
        super().__init__(
            status_code=409,
            code="invalid_offer_transition",
            message="The offer is no longer pending.",
            details={"current_status": current_status, "command": command},
        )
