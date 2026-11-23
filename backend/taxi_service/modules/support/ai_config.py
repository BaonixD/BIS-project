from typing import Annotated

from fastapi import Depends, Request
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from taxi_service.modules.support.ai_knowledge import DEFAULT_SYSTEM_PROMPT


class SupportAISettings(BaseSettings):
    """``SUPPORT_AI_ENABLED`` with a ``GEMINI_API_KEY`` turns the FAQ assistant on."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    enabled: bool = Field(default=False, validation_alias="SUPPORT_AI_ENABLED")
    model: str = Field(
        default="gemini-2.5-flash",
        pattern=r"^[a-z0-9][a-z0-9.\-]{0,63}$",
        validation_alias="GEMINI_MODEL",
    )
    api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    max_output_tokens: int = Field(
        default=2048, ge=64, le=8192, validation_alias="LLM_MAX_OUTPUT_TOKENS"
    )
    timeout_s: float = Field(default=60, gt=0, le=120, validation_alias="LLM_TIMEOUT_SECONDS")
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT, validation_alias="LLM_SYSTEM_PROMPT")
    queue_limit: int = Field(default=20, ge=1, le=200, validation_alias="SUPPORT_AI_QUEUE_LIMIT")
    interval_s: float = Field(default=1.0, gt=0, le=60, validation_alias="SUPPORT_AI_INTERVAL_S")

    @field_validator("api_key", mode="before")
    @classmethod
    def blank_key_means_unset(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("system_prompt", mode="before")
    @classmethod
    def blank_prompt_means_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return DEFAULT_SYSTEM_PROMPT
        return value

    @property
    def active(self) -> bool:
        return self.enabled and self.api_key is not None


def support_ai_settings(request: Request) -> SupportAISettings:
    settings: SupportAISettings = request.app.state.support_ai_settings
    return settings


SupportAIDep = Annotated[SupportAISettings, Depends(support_ai_settings)]
