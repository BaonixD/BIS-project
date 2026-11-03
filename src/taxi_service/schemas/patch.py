from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class PatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _reject_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("null is not allowed; omit the field to keep its value")
        return value

    def changes(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.model_fields_set}
