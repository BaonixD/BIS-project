from pydantic import BaseModel, Field, JsonValue


class ErrorBody(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Resource not found."])
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Unified error envelope returned by every non-2xx API response."""

    error: ErrorBody
    request_id: str
