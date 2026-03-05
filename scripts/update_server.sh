#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

REMOTE="${NBS_REMOTE:-origin}"
BRANCH="${NBS_BRANCH:-main}"
CHECK_URL="${NBS_CHECK_URL:-http://127.0.0.1:18080}"

log() {
  echo "[update] $*"
}

fail() {
  echo "[update][error] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

resolve_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  fail "docker compose is not available"
}

require_cmd git
require_cmd docker
require_cmd curl

if [ ! -f ".env.nbs" ]; then
  fail ".env.nbs not found in project root: $PROJECT_ROOT"
fi

if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]; then
  fail "current branch is not '$BRANCH' (set NBS_BRANCH if needed)"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "local changes detected; commit/stash them before update"
fi

COMPOSE_CMD="$(resolve_compose_cmd)"

log "fetching latest code from $REMOTE/$BRANCH"
git fetch "$REMOTE" --prune
git pull --ff-only "$REMOTE" "$BRANCH"

log "building and starting docker services"
if [ "$COMPOSE_CMD" = "docker compose" ]; then
  docker compose up -d --build
  docker compose ps
else
  docker-compose up -d --build
  docker-compose ps
fi

log "waiting for service health: $CHECK_URL"
for _ in $(seq 1 30); do
  if curl -fsS "$CHECK_URL" >/dev/null; then
    log "health check passed"
    exit 0
  fi
  sleep 2
done

if [ "$COMPOSE_CMD" = "docker compose" ]; then
  docker compose logs --tail=120 || true
else
  docker-compose logs --tail=120 || true
fi
fail "health check failed: $CHECK_URL"
