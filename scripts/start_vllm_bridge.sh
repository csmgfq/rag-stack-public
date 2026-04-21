#!/usr/bin/env bash
set -euo pipefail

VLLM_PORT="${VLLM_BRIDGE_PORT:-8000}"
LMSTUDIO_HOST="${LMSTUDIO_FALLBACK_HOST:-100.66.142.110}"
LMSTUDIO_PORT="${LMSTUDIO_FALLBACK_PORT:-1234}"

if command -v ss >/dev/null 2>&1; then
  if ss -lnt | grep -q ":${VLLM_PORT} "; then
    echo "[start_vllm_bridge] port ${VLLM_PORT} already listening"
    exit 0
  fi
fi

nohup socat "TCP-LISTEN:${VLLM_PORT},bind=127.0.0.1,reuseaddr,fork" "TCP:${LMSTUDIO_HOST}:${LMSTUDIO_PORT}" >/tmp/vllm_bridge.log 2>&1 &
echo "[start_vllm_bridge] bridge up 127.0.0.1:${VLLM_PORT} -> ${LMSTUDIO_HOST}:${LMSTUDIO_PORT}"
