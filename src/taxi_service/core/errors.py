from collections.abc import Mapping

from pydantic import JsonValue


class AppError(Exception):
    """Expected application error rendered as the unified API error response.

    ``details`` is sent to the client and must never contain secrets.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = dict(details or {})
