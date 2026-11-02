"""Payment domain errors rendered by the unified API error handler."""

from taxi_service.core.errors import AppError


class PaymentActionForbiddenError(AppError):
    def __init__(self, *, action: str) -> None:
        super().__init__(
            status_code=403,
            code="payment_action_forbidden",
            message="This payment action is not allowed for you.",
            details={"action": action},
        )


class RideNotCompletedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="ride_not_completed",
            message="Payment actions are available only after the ride is completed.",
        )


class InvalidPaymentTransitionError(AppError):
    def __init__(self, *, action: str, method: str, status: str) -> None:
        super().__init__(
            status_code=409,
            code="invalid_payment_transition",
            message="This payment action is not possible in the current payment state.",
            details={"action": action, "method": method, "status": status},
        )


class KaspiUnavailableError(AppError):
    """No valid ``KASPI_PAYMENT_URL`` is configured; cash keeps working."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="kaspi_unavailable",
            message="Kaspi payment is not available.",
        )


class ConfirmationReferenceRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            code="confirmation_reference_required",
            message="Kaspi confirmation requires a reconciliation note or POS reference.",
        )


class InvalidConfirmationReferenceError(AppError):
    def __init__(self, *, max_length: int) -> None:
        super().__init__(
            status_code=422,
            code="invalid_confirmation_reference",
            message=(
                "The confirmation note must be plain text without control characters "
                f"and at most {max_length} characters."
            ),
            details={"max_length": max_length},
        )
