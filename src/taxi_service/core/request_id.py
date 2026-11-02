import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_HEADER_KEY = REQUEST_ID_HEADER.lower().encode("latin-1")
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """Request ID of the HTTP request being handled in this context, if any."""
    return _request_id.get()


class RequestIdMiddleware:
    """Assigns a request ID, exposes it in ``request.state`` and the response header.

    A client-supplied ``X-Request-ID`` is reused only if it is short and limited to
    ``[A-Za-z0-9._-]``, so it is safe to put into logs and headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        token = _request_id.set(request_id)
        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id.reset(token)


def _resolve_request_id(scope: Scope) -> str:
    for name, value in scope["headers"]:
        if name == _REQUEST_ID_HEADER_KEY:
            candidate: str = value.decode("latin-1")
            if _SAFE_REQUEST_ID.fullmatch(candidate):
                return candidate
            break
    return uuid.uuid4().hex
