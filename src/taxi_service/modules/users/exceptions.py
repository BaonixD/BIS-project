from taxi_service.core.errors import AppError


class UsernameTakenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409, code="username_taken", message="This username is already taken."
        )
