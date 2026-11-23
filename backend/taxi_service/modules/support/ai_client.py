"""One ``generateContent`` call to Gemini; failures carry a short code and no provider text."""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

import httpx

from taxi_service.modules.support.ai_config import SupportAISettings

GEMINI_BASE_URL: Final = "https://generativelanguage.googleapis.com"
MAX_REPLY_CHARS: Final = 2000


@dataclass(frozen=True, slots=True)
class Turn:
    role: Literal["user", "model"]
    text: str


class AIReplyError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SupportAIProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def reply(self, *, system: str, turns: Sequence[Turn]) -> str: ...


def create_gemini_http_client(settings: SupportAISettings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=GEMINI_BASE_URL,
        timeout=httpx.Timeout(settings.timeout_s, connect=min(10.0, settings.timeout_s)),
    )


class GeminiProvider:
    def __init__(self, settings: SupportAISettings, http: httpx.AsyncClient) -> None:
        if settings.api_key is None:
            raise ValueError("GEMINI_API_KEY is not configured")
        self._settings = settings
        self._http = http

    @property
    def model(self) -> str:
        return self._settings.model

    async def reply(self, *, system: str, turns: Sequence[Turn]) -> str:
        try:
            async with asyncio.timeout(self._settings.timeout_s):
                response = await self._http.post(
                    f"/v1beta/models/{self.model}:generateContent",
                    headers=self._headers(),
                    json=self._payload(system, turns),
                )
        except (TimeoutError, httpx.TimeoutException):
            raise AIReplyError("timeout") from None
        except httpx.HTTPError:
            raise AIReplyError("network_error") from None
        if response.status_code != 200:
            raise AIReplyError(_status_code(response.status_code))
        try:
            data = response.json()
        except ValueError:
            raise AIReplyError("invalid_response") from None
        return reply_text(data)

    def _headers(self) -> dict[str, str]:
        assert self._settings.api_key is not None
        return {"x-goog-api-key": self._settings.api_key.get_secret_value()}

    def _payload(self, system: str, turns: Sequence[Turn]) -> dict[str, Any]:
        config: dict[str, Any] = {"maxOutputTokens": self._settings.max_output_tokens}
        if self.model.startswith("gemini-2.5-flash"):
            config["thinkingConfig"] = {"thinkingBudget": 0}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": turn.role, "parts": [{"text": turn.text}]} for turn in turns],
            "generationConfig": config,
        }


def _status_code(status: int) -> str:
    if status in (401, 403):
        return "unauthorized"
    if status == 404:
        return "model_not_found"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "provider_unavailable"
    return "bad_request"


def reply_text(data: object) -> str:
    """The finished plain-text answer of a ``generateContent`` response."""
    if not isinstance(data, dict):
        raise AIReplyError("invalid_response")
    feedback = data.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        raise AIReplyError("blocked")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise AIReplyError("empty")
    candidate = candidates[0]
    reason = candidate.get("finishReason")
    if reason == "MAX_TOKENS":
        raise AIReplyError("truncated")
    if reason != "STOP":
        raise AIReplyError("blocked" if reason else "invalid_response")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise AIReplyError("empty")
    text = "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
    )
    text = plain_text(text)
    if not text:
        raise AIReplyError("empty")
    if len(text) > MAX_REPLY_CHARS:
        raise AIReplyError("too_long")
    return text


# The prompt asks for plain text; models still slip into Markdown or echo bracketed tags.
_TAG_LINE = re.compile(r"^\s*\[[^\]\n]{1,60}\]\s*$")
_TAG_PREFIX = re.compile(r"^\s*\[(?:Тема|Topic|Тақырып)\b[^\]\n]*\]\s*", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BULLET = re.compile(r"^(\s*)[*+\-]\s+")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])")
_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>\n]*>")


def plain_text(text: str) -> str:
    """The reply as chat text: no Markdown marks, HTML tags or echoed service tags."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = _TAG_PREFIX.sub("", _TAG_LINE.sub("", raw.rstrip()))
        line = _HEADING.sub("", line)
        line = _BULLET.sub(r"\1• ", line)
        line = _BOLD.sub(lambda match: match.group(1) or match.group(2), line)
        line = _ITALIC.sub(r"\1", line)
        line = _CODE.sub(r"\1", line)
        line = _LINK.sub(r"\1 (\2)", line)
        line = _HTML_TAG.sub("", line)
        if raw.strip() and not line.strip():
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
