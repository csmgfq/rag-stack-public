#!/usr/bin/env bash
set -euo pipefail

ROUTER_BASE_URL="${ROUTER_BASE_URL:-http://127.0.0.1:18000}"

echo "== health =="
curl -sS "$ROUTER_BASE_URL/health" | python3 -m json.tool

echo "== request #1 (expect cache miss) =="
curl -sS "$ROUTER_BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "rag-main",
    "messages": [{"role": "user", "content": "请用一句话解释什么是RAG"}],
    "max_tokens": 64,
    "top_k": 20,
    "filters": {"tenant": "default"}
  }' | python3 -m json.tool

echo "== request #2 (expect cache hit) =="
curl -sS "$ROUTER_BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "rag-main",
    "messages": [{"role": "user", "content": "请用一句话解释什么是RAG"}],
    "max_tokens": 64,
    "top_k": 20,
    "filters": {"tenant": "default"}
  }' | python3 -m json.tool
