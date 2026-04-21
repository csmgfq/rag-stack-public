#!/usr/bin/env bash
set -euo pipefail

# Safety default: do not stop existing services unless explicitly requested.
if [[ "${1:-}" != "--force-stop-legacy" ]]; then
  echo "[stack_down] skipped by default to avoid breaking existing services."
  echo "Use: bash scripts/stack_down.sh --force-stop-legacy"
  exit 0
fi

LEGACY_STOP="/home/jiangzhiming/workspace/llm/rag/monitoring/nosudo/stop_nosudo_monitoring.sh"
if [[ -x "$LEGACY_STOP" ]]; then
  bash "$LEGACY_STOP"
fi

echo "[stack_down] legacy services stopped"
