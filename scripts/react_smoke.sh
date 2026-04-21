#!/usr/bin/env bash
set -euo pipefail

REACT_BASE_URL="${REACT_BASE_URL:-http://127.0.0.1:18001/v1}"
ROUTER_BASE_URL="${ROUTER_BASE_URL:-http://127.0.0.1:18000}"
MODEL="${REACT_SMOKE_MODEL:-react-agent}"

curl -fsS "${REACT_BASE_URL}/models" | python3 -m json.tool >/dev/null

curl -fsS "${ROUTER_BASE_URL}/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"route\":\"react\",\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"请基于资料解释RAG的核心思想\"}],\"max_tokens\":128}" \
  | python3 -m json.tool >/dev/null

echo "[react_smoke] passed react=${REACT_BASE_URL} router=${ROUTER_BASE_URL}"
