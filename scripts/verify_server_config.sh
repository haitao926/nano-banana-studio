#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18080}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin888}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FAILURES=0

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; FAILURES=$((FAILURES + 1)); }

login_file="$TMP_DIR/login.json"
login_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$login_file" -w "%{http_code}" \
  -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=$ADMIN_USER&password=$ADMIN_PASS" || true)"

if [[ "$login_code" != "200" ]]; then
  echo "Login failed: HTTP $login_code"
  cat "$login_file" 2>/dev/null || true
  exit 1
fi

TOKEN="$(jq -r '.access_token // empty' "$login_file")"
if [[ -z "$TOKEN" ]]; then
  echo "Login succeeded but token missing."
  cat "$login_file"
  exit 1
fi
pass "admin login ok"

auth_header=(-H "Authorization: Bearer $TOKEN")

cfg_file="$TMP_DIR/system_config.json"
cfg_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$cfg_file" -w "%{http_code}" \
  "$BASE_URL/api/admin/system_config" "${auth_header[@]}" || true)"

if [[ "$cfg_code" != "200" ]]; then
  fail "GET /api/admin/system_config failed: HTTP $cfg_code"
  cat "$cfg_file" 2>/dev/null || true
  exit 1
fi
pass "system config fetched"

has_model() {
  local model="$1"
  jq -e --arg m "$model" '.models[] | select(.model == $m and (.enabled == true))' "$cfg_file" >/dev/null 2>&1
}

if has_model "gpt-image-1.5"; then
  fail "gpt-image-1.5 should be removed, but still exists in system config"
else
  pass "gpt-image-1.5 removed"
fi

for model in \
  "gemini-3.1-flash-image-preview" \
  "gemini-3-pro-image-preview" \
  "doubao-seedream-5-0-260128" \
  "z-image-turbo" \
  "gpt-image-1.5-all" \
  "gemini-3.1-pro-preview" \
  "claude-sonnet-4-6" \
  "gpt-5.2-chat" \
  "kimi-k2.5"
do
  if has_model "$model"; then
    pass "model enabled: $model"
  else
    fail "model missing/disabled: $model"
  fi
done

for ch in google bytedance aliyun; do
  if jq -e --arg ch "$ch" '.prompt_channels[$ch]' "$cfg_file" >/dev/null 2>&1; then
    pass "prompt channel exists: $ch"
  else
    fail "prompt channel missing: $ch"
  fi
done

prompt_health_file="$TMP_DIR/prompt_health.json"
prompt_health_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$prompt_health_file" -w "%{http_code}" \
  "$BASE_URL/api/admin/prompt_health" "${auth_header[@]}" || true)"
if [[ "$prompt_health_code" == "200" ]]; then
  pass "prompt health endpoint ok"
  jq -r '.channels | to_entries[] | "  - \(.key): \(.value.status) (selected=\(.value.selected_model // "n/a"))"' "$prompt_health_file" || true
else
  warn "prompt health endpoint failed: HTTP $prompt_health_code"
  cat "$prompt_health_file" 2>/dev/null || true
fi

test_prompt_channel() {
  local channel="$1"
  local out_file="$TMP_DIR/prompt_${channel}.json"
  local code
  code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$out_file" -w "%{http_code}" \
    -X POST "$BASE_URL/api/optimize_prompt" \
    -H "Content-Type: application/json" \
    "${auth_header[@]}" \
    -d "$(jq -nc --arg c "$channel" '{prompt:"高中数学矩阵乘法教学海报",subject:"general",channel:$c}')" || true)"
  if [[ "$code" == "200" ]]; then
    local hit_model
    hit_model="$(jq -r '.model // "n/a"' "$out_file")"
    pass "prompt channel $channel ok (hit=$hit_model)"
  else
    local detail
    detail="$(jq -r '.detail // .message // "unknown error"' "$out_file" | tr '\n' ' ' | cut -c1-200)"
    fail "prompt channel $channel failed: HTTP $code, $detail"
  fi
}

test_image_model() {
  local model="$1"
  local platform="$2"
  local size="$3"
  local out_file="$TMP_DIR/image_${model}.json"
  local payload
  payload="$(jq -nc --arg m "$model" --arg p "$platform" --arg s "$size" \
    '{service:"image",model:$m,platform:$p,prompt:"test image: red apple on white background",size:$s}')"
  local code
  code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$out_file" -w "%{http_code}" \
    -X POST "$BASE_URL/api/admin/model_test" \
    -H "Content-Type: application/json" \
    "${auth_header[@]}" \
    -d "$payload" || true)"
  if [[ "$code" == "200" ]]; then
    local url
    url="$(jq -r '.result.url // empty' "$out_file")"
    if [[ -n "$url" ]]; then
      pass "image model $model ok"
    else
      fail "image model $model returned 200 but url missing"
    fi
  else
    local detail
    detail="$(jq -r '.detail // .message // "unknown error"' "$out_file" | tr '\n' ' ' | cut -c1-220)"
    fail "image model $model failed: HTTP $code, $detail"
  fi
}

echo "Running prompt tests..."
test_prompt_channel "google"
sleep 2
test_prompt_channel "bytedance"
sleep 2
test_prompt_channel "aliyun"
sleep 2

echo "Running image tests..."
test_image_model "gemini-3.1-flash-image-preview" "vector" "1024x1024"
sleep 2
test_image_model "gpt-image-1.5-all" "vector" "1024x1024"
sleep 2
test_image_model "z-image-turbo" "bailian" "1024x1024"
sleep 2
test_image_model "doubao-seedream-5-0-260128" "ark" "2K"

echo
if [[ "$FAILURES" -eq 0 ]]; then
  echo "Verification finished: ALL CHECKS PASSED."
  exit 0
fi

echo "Verification finished: $FAILURES check(s) failed."
exit 1
