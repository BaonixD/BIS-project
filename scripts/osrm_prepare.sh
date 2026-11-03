#!/usr/bin/env bash
# Usage: scripts/osrm_prepare.sh — download OSM data for Kazakhstan, cut the Almaty
# agglomeration and build the OSRM car graph in infra/osrm/data (ADR 0014).
# Safe to rerun: the source is downloaded again only when Geofabrik has a newer one,
# the graph is rebuilt and a running osrm container is restarted on the new map.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT/infra/osrm/data"
COMPOSE_FILE="$ROOT/infra/osrm/docker-compose.yml"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v6.0.0"
SOURCE_URL="https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf"
SOURCE="$DATA_DIR/kazakhstan-latest.osm.pbf"
# Kaskelen / SDU in the west ... Talgar in the east.
ALMATY_BBOX="76.45,43.05,77.35,43.45"
REGION="$DATA_DIR/almaty.osm.pbf"
GRAPH="almaty.osrm"
BUILD_MEMORY="2g"

step() { printf '\n==> %s\n' "$*"; }
fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_tools() {
  command -v curl >/dev/null || fail "curl is required"
  command -v osmium >/dev/null || fail "osmium is required: brew install osmium-tool"
  command -v docker >/dev/null || fail "docker is required (Docker Desktop)"
  docker info >/dev/null 2>&1 || fail "the Docker daemon is not running: start Docker Desktop"
}

download_source() {
  step "Downloading $SOURCE_URL (only when Geofabrik has a newer file)"
  local partial="$SOURCE.part"
  local condition=()
  if [[ -f "$SOURCE" ]]; then condition=(--time-cond "$SOURCE"); fi
  rm -f "$partial"
  curl --fail --location --retry 3 --remote-time ${condition[@]+"${condition[@]}"} \
    --output "$partial" "$SOURCE_URL"
  if [[ -s "$partial" ]]; then
    verify_md5 "$partial"
    mv "$partial" "$SOURCE"
  else
    rm -f "$partial"
    echo "Up to date: $(basename "$SOURCE")"
  fi
}

verify_md5() {
  local expected actual
  expected="$(curl --fail --location --retry 3 --silent "$SOURCE_URL.md5" | awk '{print $1}')"
  actual="$(md5 -q "$1" 2>/dev/null || md5sum "$1" | awk '{print $1}')"
  [[ -n "$expected" && "$expected" == "$actual" ]] ||
    fail "MD5 of the download does not match $SOURCE_URL.md5; rerun the script"
  echo "MD5 ok: $actual"
}

cut_region() {
  step "Cutting the Almaty agglomeration, bbox $ALMATY_BBOX"
  osmium extract --bbox "$ALMATY_BBOX" --strategy complete_ways --overwrite \
    --output "$REGION" "$SOURCE"
  ls -lh "$REGION"
}

osrm_tool() {
  docker run --rm --memory "$BUILD_MEMORY" --volume "$DATA_DIR:/data" "$OSRM_IMAGE" "$@"
}

build_graph() {
  step "Building the OSRM car graph: extract, partition, customize"
  rm -f "$DATA_DIR/$GRAPH" "$DATA_DIR/$GRAPH".*
  osrm_tool osrm-extract -p /opt/car.lua "/data/$(basename "$REGION")"
  osrm_tool osrm-partition "/data/$GRAPH"
  osrm_tool osrm-customize "/data/$GRAPH"
}

restart_running_server() {
  local running
  running="$(docker compose -f "$COMPOSE_FILE" ps --quiet --status running osrm 2>/dev/null || true)"
  if [[ -n "$running" ]]; then
    step "Restarting the running osrm container on the new map"
    docker compose -f "$COMPOSE_FILE" restart osrm
  else
    echo "Start the server: docker compose -f infra/osrm/docker-compose.yml up -d"
  fi
}

main() {
  require_tools
  mkdir -p "$DATA_DIR"
  download_source
  cut_region
  build_graph
  restart_running_server
  step "Done: $DATA_DIR/$GRAPH"
}

main "$@"
