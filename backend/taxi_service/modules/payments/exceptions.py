from taxi_service.core.errors import AppError


class PaymentActionForbiddenError(AppError):
    def __init__(self, *, action: str) -> None:
        super().__init__(
            status_code=403,
            code="payment_action_forbidden",
            message="Only the ride's assigned driver can do this with its payment.",
            details={"action": action},
        )


class RideNotCompletedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="ride_not_completed",
            message="Cash can be received only after the ride is completed.",
        )


class InvalidPaymentTransitionError(AppError):
    def __init__(self, *, action: str, status: str) -> None:
        super().__init__(
            status_code=409,
            code="invalid_payment_transition",
            message="This payment action is not possible in the current payment state.",
            details={"action": action, "status": status},
        )


class KaspiUnavailableError(AppError):
    """No valid ``KASPI_PAYMENT_URL`` is configured; cash keeps working."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503, code="kaspi_unavailable", message="Kaspi payment is not available."
        )


class PaymentNotFoundError(AppError):
    """A ride without its payment record; the order always opens one (ADR 0010)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=404, code="payment_not_found", message="The ride has no payment record."
        )
