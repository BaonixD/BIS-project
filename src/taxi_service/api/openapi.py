from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from taxi_service.modules.rides.idempotency import IDEMPOTENCY_HEADER

SAFE_METHODS = frozenset({"get", "head", "options"})
SESSION_SCHEME = "SessionCookie"
CSRF_SCHEME = "CsrfToken"


def install_openapi(app: FastAPI) -> None:
    app.openapi = _openapi_builder(app)  # type: ignore[method-assign]


def _openapi_builder(app: FastAPI) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            describe_requirements(schema)
            app.openapi_schema = schema
        return app.openapi_schema

    return build


def describe_requirements(schema: dict[str, Any]) -> None:
    # FastAPI lists API-key dependencies as alternatives and cannot mark Idempotency-Key required.
    for item in schema.get("paths", {}).values():
        for method, operation in item.items():
            _describe_security(method, operation)
            _require_idempotency_key(operation)


def _describe_security(method: str, operation: dict[str, Any]) -> None:
    schemes = {name for requirement in operation.get("security", []) for name in requirement}
    if SESSION_SCHEME not in schemes:
        return
    if method in SAFE_METHODS:
        operation["security"] = [{SESSION_SCHEME: []}]
    else:
        operation["security"] = [{SESSION_SCHEME: [], CSRF_SCHEME: []}]


def _require_idempotency_key(operation: dict[str, Any]) -> None:
    for parameter in operation.get("parameters", []):
        if parameter.get("in") == "header" and parameter.get("name") == IDEMPOTENCY_HEADER:
            parameter["required"] = True
