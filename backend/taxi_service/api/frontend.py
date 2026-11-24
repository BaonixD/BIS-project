"""Serves the built web app (frontend/dist) from the API process: one container, one domain.

Unknown paths get index.html (client-side routes); /api and /health never fall back to it.
The service worker, index.html and the precache list must not be cached by browsers, or a
release would never reach installed apps; hashed /assets files are immutable.
"""

from pathlib import Path
from typing import Final

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

NO_CACHE_FILES: Final = frozenset(
    {"sw.js", "index.html", "precache.json", "manifest.webmanifest", "offline.html"}
)
API_PREFIXES: Final = ("api/", "api", "health/", "health")


def cache_control(relative: str) -> str:
    if relative.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    if relative in NO_CACHE_FILES:
        return "no-cache"
    return "public, max-age=3600"


def install_frontend(app: FastAPI, dist: Path) -> None:
    root = dist.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST has no index.html: {root}")

    async def serve(request: Request) -> FileResponse:
        path: str = request.path_params["path"]
        if path.startswith(API_PREFIXES):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        found = path and candidate.is_file() and candidate.is_relative_to(root)
        file = candidate if found else index
        relative = file.relative_to(root).as_posix()
        return FileResponse(file, headers={"Cache-Control": cache_control(relative)})

    app.add_api_route("/{path:path}", serve, methods=["GET", "HEAD"], include_in_schema=False)
