#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18080}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin888}"
ASSISTANT_MODEL="${ASSISTANT_MODEL:-kimi-k2.5}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"
MAX_TOOL_ROUNDS="${MAX_TOOL_ROUNDS:-4}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required."
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FAILURES=0
WARNINGS=0

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "[FAIL] $*"; FAILURES=$((FAILURES + 1)); }

read_json_field() {
  local json_file="$1"
  local field_path="$2"
  python3 - "$json_file" "$field_path" <<'PY'
import json
import sys

f = sys.argv[1]
path = sys.argv[2].split(".")
try:
    data = json.load(open(f, "r", encoding="utf-8"))
except Exception:
    print("")
    sys.exit(0)

cur = data
for key in path:
    if isinstance(cur, dict):
        cur = cur.get(key)
    else:
        cur = None
        break

if cur is None:
    print("")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
else:
    print(str(cur))
PY
}

read_tool_events_count() {
  local json_file="$1"
  python3 - "$json_file" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
except Exception:
    print("0")
    sys.exit(0)

events = data.get("tool_events")
if isinstance(events, list):
    print(len(events))
else:
    print("0")
PY
}

pretty_error() {
  local json_file="$1"
  python3 - "$json_file" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
except Exception:
    print("")
    sys.exit(0)

if isinstance(data, dict):
    detail = data.get("detail") or data.get("message") or ""
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("msg") or str(detail)
    print(str(detail)[:300])
else:
    print(str(data)[:300])
PY
}

echo "== Step 1: login =="
login_file="$TMP_DIR/login.json"
login_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$login_file" -w "%{http_code}" \
  -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=$ADMIN_USER&password=$ADMIN_PASS" || true)"

if [[ "$login_code" != "200" ]]; then
  fail "login failed: HTTP $login_code, $(pretty_error "$login_file")"
  echo "Verification finished: $FAILURES failed, $WARNINGS warnings."
  exit 1
fi

TOKEN="$(read_json_field "$login_file" "access_token")"
if [[ -z "$TOKEN" ]]; then
  fail "login succeeded but access_token is missing"
  echo "Verification finished: $FAILURES failed, $WARNINGS warnings."
  exit 1
fi
pass "login ok"

echo "== Step 2: tool_calls first turn =="
chat1_file="$TMP_DIR/chat1.json"
chat1_payload="$TMP_DIR/chat1_payload.json"
cat > "$chat1_payload" <<JSON
{
  "message": "请你先调用 search 工具联网查询 Context Caching，再用 4 句话总结，并给出来源链接。",
  "model": "${ASSISTANT_MODEL}",
  "temperature": 0.2,
  "max_history_messages": 20,
  "file_ids": [],
  "enable_tools": true,
  "max_tool_rounds": ${MAX_TOOL_ROUNDS}
}
JSON

chat1_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$chat1_file" -w "%{http_code}" \
  -X POST "$BASE_URL/api/assistant/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @"$chat1_payload" || true)"

if [[ "$chat1_code" != "200" ]]; then
  fail "assistant chat (turn1) failed: HTTP $chat1_code, $(pretty_error "$chat1_file")"
  echo "Verification finished: $FAILURES failed, $WARNINGS warnings."
  exit 1
fi

turn1_message="$(read_json_field "$chat1_file" "message")"
conversation_id="$(read_json_field "$chat1_file" "conversation_id")"
tool_events_count="$(read_tool_events_count "$chat1_file")"

if [[ -n "$turn1_message" ]]; then
  pass "assistant turn1 returned message"
else
  fail "assistant turn1 message is empty"
fi

if [[ -n "$conversation_id" ]]; then
  pass "conversation_id received: $conversation_id"
else
  fail "conversation_id is missing"
fi

if [[ "$tool_events_count" -gt 0 ]]; then
  pass "tool_calls executed: $tool_events_count event(s)"
else
  warn "tool_events is 0 (model may answer directly without tool call)"
fi

echo "== Step 3: multi-turn memory check =="
chat2_file="$TMP_DIR/chat2.json"
chat2_payload="$TMP_DIR/chat2_payload.json"
cat > "$chat2_payload" <<JSON
{
  "message": "请用一句话复述你刚刚给我的总结核心。",
  "conversation_id": "${conversation_id}",
  "model": "${ASSISTANT_MODEL}",
  "temperature": 0.2,
  "max_history_messages": 20,
  "file_ids": [],
  "enable_tools": false,
  "max_tool_rounds": 1
}
JSON

chat2_code="$(curl -sS -m "$TIMEOUT_SECONDS" -o "$chat2_file" -w "%{http_code}" \
  -X POST "$BASE_URL/api/assistant/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @"$chat2_payload" || true)"

if [[ "$chat2_code" != "200" ]]; then
  fail "assistant chat (turn2) failed: HTTP $chat2_code, $(pretty_error "$chat2_file")"
else
  turn2_message="$(read_json_field "$chat2_file" "message")"
  if [[ -n "$turn2_message" ]]; then
    pass "assistant turn2 returned message (multi-turn works)"
  else
    fail "assistant turn2 message is empty"
  fi
fi

echo
echo "== Summary =="
echo "BASE_URL: $BASE_URL"
echo "MODEL: $ASSISTANT_MODEL"
echo "conversation_id: ${conversation_id:-n/a}"
echo "tool_events_count(turn1): ${tool_events_count:-0}"
echo "assistant_turn1_preview: ${turn1_message:0:120}"

if [[ "$FAILURES" -eq 0 ]]; then
  echo "Verification finished: ALL CORE CHECKS PASSED. (warnings=$WARNINGS)"
  exit 0
fi

echo "Verification finished: $FAILURES failed, $WARNINGS warnings."
exit 1
