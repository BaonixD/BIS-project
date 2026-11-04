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


class OfferNotFoundError(AppError):
    """No offer with this id, or it was made to another driver; both look the same."""

    def __init__(self) -> None:
        super().__init__(status_code=404, code="offer_not_found", message="Offer not found.")


class OfferExpiredError(AppError):
    """The offer's time is up (``now >= expires_at``), whether or not the loop marked it."""

    def __init__(self) -> None:
        super().__init__(status_code=409, code="offer_expired", message="The offer has expired.")


class DriverBusyError(AppError):
    """The driver already has an accepted active ride; a second one is never assigned."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="driver_busy",
            message="The driver already has an active ride.",
        )


class QuoteNotFoundError(AppError):
    """No quote with this id, or it belongs to another passenger; both look the same."""

    def __init__(self) -> None:
        super().__init__(status_code=404, code="quote_not_found", message="Quote not found.")


class QuoteExpiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="quote_expired",
            message="The quote has expired; request a new one.",
        )


class QuoteAlreadyUsedError(AppError):
    """Another request (another Idempotency-Key) already created a ride from this quote."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="quote_already_used",
            message="A ride was already created from this quote.",
        )


class ActiveRideExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="active_ride_exists",
            message="The passenger already has an active ride.",
        )


class IdempotencyKeyRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="idempotency_key_required",
            message="The Idempotency-Key header is required.",
        )


class IdempotencyKeyInvalidError(AppError):
    """The key is not 1..128 visible ASCII characters; the value is not echoed."""

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="idempotency_key_invalid",
            message="Idempotency-Key must be 1 to 128 visible ASCII characters.",
        )


class IdempotencyKeyReusedError(AppError):
    """The key was already used by this user for a request with another body."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="idempotency_key_reused",
            message="This Idempotency-Key was already used with a different request.",
        )


class InvalidDateRangeError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="invalid_date_range",
            message="created_from must not be later than created_to.",
        )
