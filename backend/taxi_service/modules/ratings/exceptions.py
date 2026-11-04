from collections.abc import Sequence

from taxi_service.core.errors import AppError


class RatingForbiddenError(AppError):
    """An admin sees the ride but only its passenger and driver rate it."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            code="rating_forbidden",
            message="Only the ride's passenger and its driver can rate it.",
        )


class RideNotCompletedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="ride_not_completed",
            message="A ride can be rated only after it is completed.",
        )


class RatingAlreadyExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="rating_already_exists",
            message="This side of the ride has already rated it.",
        )


class RatingTagsNotAllowedError(AppError):
    """Same envelope as a request validation error: a tag of the other side is a bad value."""

    def __init__(self, positions: Sequence[int], allowed: Sequence[str]) -> None:
        super().__init__(
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details={
                "errors": [
                    {
                        "loc": ["body", "tags", position],
                        "msg": f"Tag must be one of: {', '.join(allowed)}",
                        "type": "rating_tag_not_allowed",
                    }
                    for position in positions
                ]
            },
        )
