from taxi_service.core.errors import AppError


class UserNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(status_code=404, code="user_not_found", message="User not found.")


class AdminAccountProtectedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="admin_account_protected",
            message="Administrator accounts cannot be blocked.",
        )


class AccountHasActiveRideError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="account_has_active_ride",
            message="Finish active rides and collect outstanding cash before blocking.",
        )
