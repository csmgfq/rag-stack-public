#!/usr/bin/env bash
set -euo pipefail

VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL="${VLLM_SMOKE_MODEL:-google/gemma-4-e4b}"

echo "== vLLM models =="
curl -fsS "$VLLM_BASE_URL/models" | python3 -m json.tool >/dev/null

echo "== vLLM chat completion =="
curl -fsS "$VLLM_BASE_URL/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"请用一句话介绍RAG\"}],\"max_tokens\":64}" \
  | python3 -m json.tool >/dev/null

echo "[vllm_smoke] passed base=$VLLM_BASE_URL model=$MODEL"
