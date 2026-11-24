# TulparTaxi in one container: the built web app and the API on the same port (Dokploy-ready).
# Data (SQLite and driver documents) lives in /data — mount a persistent volume there.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    FRONTEND_DIST=/app/frontend/dist \
    DATABASE_URL=sqlite+aiosqlite:////data/tulpar.db \
    DOCUMENT_STORAGE_DIR=/data/driver-documents \
    SESSION_COOKIE_SECURE=true
VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "scripts/docker-start.sh"]
