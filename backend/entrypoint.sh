#!/bin/sh
set -e

HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-8000}"
WORKERS="${UVICORN_WORKERS:-2}"

exec uvicorn main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"
