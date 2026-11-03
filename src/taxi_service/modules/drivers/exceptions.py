from taxi_service.core.errors import AppError


class DriverNotFoundError(AppError):
    """No user with this id, or the user is not a driver."""

    def __init__(self) -> None:
        super().__init__(status_code=404, code="driver_not_found", message="Driver not found.")


class DriverProfileIncompleteError(AppError):
    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__(
            status_code=409,
            code="driver_profile_incomplete",
            message="The driver profile or vehicle is incomplete.",
            details={"missing_fields": list(missing_fields)},
        )


class DriverNotApprovedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="driver_not_approved",
            message="Only a driver approved by an admin can go online.",
        )


class DriverOnActiveRideError(AppError):
    """Offline and profile or car changes wait until the accepted ride ends (ADR 0007)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="driver_on_active_ride",
            message="The driver has an active ride; complete or release it first.",
        )


class PlateNumberTakenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="plate_number_taken",
            message="This plate number is registered to another driver.",
        )


class VehicleYearOutOfRangeError(AppError):
    """Same envelope as a request validation error: the year is a bad field value."""

    def __init__(self, min_year: int, max_year: int) -> None:
        super().__init__(
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details={
                "errors": [
                    {
                        "loc": ["body", "vehicle", "year"],
                        "msg": f"Model year must be between {min_year} and {max_year}",
                        "type": "vehicle_year_out_of_range",
                    }
                ]
            },
        )
