#!/bin/sh
# Container entry: bring the SQLite schema up to date, then run one API worker.
# One worker on purpose: the dispatch loop and the support AI loop live in this process.
set -eu
mkdir -p /data "${DOCUMENT_STORAGE_DIR:-/data/driver-documents}"
alembic upgrade head
exec uvicorn --factory taxi_service.main:create_app \
  --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="*"
