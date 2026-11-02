from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class PatchRequest(BaseModel):
    """Body of a partial update (PATCH).

    Omitted fields stay unchanged; ``null`` is not a value and unknown fields
    (``role``, ``id``, approval...) are rejected, both with 422. Subclasses
    declare every field as ``T | None = None``.
    """

    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _reject_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("null is not allowed; omit the field to keep its value")
        return value

    def changes(self) -> dict[str, Any]:
        """Only the fields the client sent."""
        return {name: getattr(self, name) for name in self.model_fields_set}
