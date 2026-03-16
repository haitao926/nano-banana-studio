#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

REMOTE="${NBS_REMOTE:-origin}"
REMOTE_URL="${NBS_REPO_URL:-}"
BRANCH="${NBS_BRANCH:-main}"
CHECK_URL="${NBS_CHECK_URL:-http://127.0.0.1:18080}"
ALLOW_DIRTY="${NBS_ALLOW_DIRTY:-0}"
COMPOSE_OVERRIDE="${NBS_COMPOSE_CMD:-}"

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
  if [ -n "$COMPOSE_OVERRIDE" ]; then
    echo "$COMPOSE_OVERRIDE"
    return 0
  fi
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

compose() {
  if [ "$COMPOSE_CMD" = "docker compose" ]; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

ensure_remote() {
  local current_url=""
  if git remote get-url "$REMOTE" >/dev/null 2>&1; then
    current_url="$(git remote get-url "$REMOTE")"
    if [ -n "$REMOTE_URL" ] && [ "$current_url" != "$REMOTE_URL" ]; then
      log "updating git remote '$REMOTE' -> $REMOTE_URL"
      git remote set-url "$REMOTE" "$REMOTE_URL"
    fi
    return 0
  fi

  [ -n "$REMOTE_URL" ] || fail "git remote '$REMOTE' is missing and NBS_REPO_URL is not set"
  log "creating git remote '$REMOTE' -> $REMOTE_URL"
  git remote add "$REMOTE" "$REMOTE_URL"
}

compose_build_with_retry() {
  local attempt
  local max_attempts=3
  for attempt in $(seq 1 "$max_attempts"); do
    if [ "$USE_PULL" = "1" ]; then
      log "building changed docker services with --pull (attempt $attempt/$max_attempts): ${BUILD_SERVICES[*]}"
      if compose build --pull "${BUILD_SERVICES[@]}"; then
        return 0
      fi
    else
      log "building changed docker services (attempt $attempt/$max_attempts): ${BUILD_SERVICES[*]}"
      if compose build "${BUILD_SERVICES[@]}"; then
        return 0
      fi
    fi

    if [ "$attempt" -lt "$max_attempts" ]; then
      log "docker build failed; retrying after backoff"
      sleep $((attempt * 10))
    fi
  done

  fail "docker build failed after $max_attempts attempts"
}

has_changed_path() {
  local pattern="$1"
  shift || true
  local path
  for path in "$@"; do
    case "$path" in
      $pattern)
        return 0
        ;;
    esac
  done
  return 1
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
  if [ "$ALLOW_DIRTY" = "1" ]; then
    log "warning: local changes detected, continue because NBS_ALLOW_DIRTY=1"
  else
    fail "local changes detected; commit/stash them before update (or set NBS_ALLOW_DIRTY=1)"
  fi
fi

COMPOSE_CMD="$(resolve_compose_cmd)"
ensure_remote

BEFORE_HEAD="$(git rev-parse HEAD)"
log "fetching latest code from $REMOTE/$BRANCH"
git fetch "$REMOTE" --prune
git pull --ff-only "$REMOTE" "$BRANCH"
AFTER_HEAD="$(git rev-parse HEAD)"

CHANGED_FILES=()
if [ "$BEFORE_HEAD" != "$AFTER_HEAD" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] && CHANGED_FILES+=("$line")
  done < <(git diff --name-only "$BEFORE_HEAD..$AFTER_HEAD")
fi

BUILD_SERVICES=()
UP_SERVICES=()
USE_PULL=0

if [ "${#CHANGED_FILES[@]}" -eq 0 ]; then
  log "no code changes detected; skipping image rebuild"
else
  log "changed files since last deploy:"
  printf ' - %s\n' "${CHANGED_FILES[@]}"

  if has_changed_path "backend/*" "${CHANGED_FILES[@]}" || has_changed_path "docker-compose.yml" "${CHANGED_FILES[@]}"; then
    BUILD_SERVICES+=("backend")
    UP_SERVICES+=("backend")
  fi
  if has_changed_path "frontend/*" "${CHANGED_FILES[@]}" || has_changed_path "docker-compose.yml" "${CHANGED_FILES[@]}"; then
    BUILD_SERVICES+=("frontend")
    UP_SERVICES+=("frontend")
  fi

  if has_changed_path "backend/Dockerfile" "${CHANGED_FILES[@]}" \
    || has_changed_path "frontend/Dockerfile" "${CHANGED_FILES[@]}" \
    || has_changed_path "docker-compose.yml" "${CHANGED_FILES[@]}"; then
    USE_PULL=1
  fi
fi

if [ "${#UP_SERVICES[@]}" -eq 0 ]; then
  UP_SERVICES=("backend" "frontend")
fi

if [ "${#BUILD_SERVICES[@]}" -gt 0 ]; then
  compose_build_with_retry
else
  log "no backend/frontend changes detected; skipping docker build"
fi

log "starting docker services: ${UP_SERVICES[*]}"
compose up -d "${UP_SERVICES[@]}"
compose ps

log "waiting for service health: $CHECK_URL"
for _ in $(seq 1 30); do
  if curl -fsS "$CHECK_URL" >/dev/null; then
    log "health check passed"
    exit 0
  fi
  sleep 2
done

compose logs --tail=120 || true
fail "health check failed: $CHECK_URL"
