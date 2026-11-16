from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class DocumentBodyLimit:
    """Bound the complete multipart body before Starlette spools it to disk."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "PUT"
            or not scope["path"].startswith("/api/v1/drivers/me/documents/")
        ):
            await self.app(scope, receive, send)
            return
        limit = 10 * 1024 * 1024 + 65536
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "document_too_large",
                            "message": "The PDF must be 10 MiB or smaller.",
                            "details": {},
                        },
                        "request_id": scope.get("state", {}).get("request_id", ""),
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        sent = False

        async def bounded_receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
