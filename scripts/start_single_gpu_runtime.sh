#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/scripts/runtime_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/runtime_env.sh"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${RUNTIME_VENV_DIR:-$ROOT_DIR/.venv-runtime}"
ROUTER_HOST="${RAG_ROUTER_HOST:-0.0.0.0}"
ROUTER_PORT="${RAG_ROUTER_PORT:-18000}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install -q -r "$ROOT_DIR/runtime/requirements.txt"

export RAG_MODEL_PROFILE_PATH="${RAG_MODEL_PROFILE_PATH:-$ROOT_DIR/runtime/model_profiles.json}"

"$PYTHON_BIN" -m runtime.launcher
exec uvicorn runtime.router:app --host "$ROUTER_HOST" --port "$ROUTER_PORT"
