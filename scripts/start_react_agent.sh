#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/scripts/runtime_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/runtime_env.sh"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
REACT_HOST="${REACT_AGENT_HOST:-0.0.0.0}"
REACT_PORT="${REACT_AGENT_PORT:-18001}"

exec "$PYTHON_BIN" -m uvicorn react_agent.app:app --host "$REACT_HOST" --port "$REACT_PORT"
