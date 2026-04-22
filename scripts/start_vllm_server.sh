#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Prefer conda vllm env
CONDA_BIN="${CONDA_BIN:-/opt/miniconda/bin/conda}"
VLLM_ENV="${VLLM_ENV:-vllm}"

VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_MODEL="${VLLM_MODEL:-google/gemma-4-e4b}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.92}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-16384}"
VLLM_API_KEY="${VLLM_API_KEY:-}"

# Auto-detect GPU count if TP not specified
if [[ -n "${VLLM_TP_SIZE:-}" ]]; then
  TP_SIZE="$VLLM_TP_SIZE"
else
  GPU_COUNT="$(nvidia-smi -L 2>/dev/null | wc -l | tr -d ' ')"
  if [[ -z "$GPU_COUNT" || "$GPU_COUNT" -lt 1 ]]; then
    GPU_COUNT=1
  fi
  TP_SIZE="$GPU_COUNT"
fi

EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

echo "[start_vllm_server] host=${VLLM_HOST} port=${VLLM_PORT} model=${VLLM_MODEL} tp=${TP_SIZE}"

if [[ ! -x "$CONDA_BIN" ]]; then
  echo "[start_vllm_server] conda not found at $CONDA_BIN" >&2
  exit 1
fi

# check vllm package in env
if ! "$CONDA_BIN" run -n "$VLLM_ENV" python -c "import vllm" >/dev/null 2>&1; then
  echo "[start_vllm_server] vllm package not found in conda env '$VLLM_ENV'" >&2
  echo "Install first: $CONDA_BIN run -n $VLLM_ENV pip install vllm" >&2
  exit 2
fi

ARGS=(
  serve "$VLLM_MODEL"
  --host "$VLLM_HOST"
  --port "$VLLM_PORT"
  --tensor-parallel-size "$TP_SIZE"
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
  --max-model-len "$VLLM_MAX_MODEL_LEN"
)

if [[ -n "$VLLM_API_KEY" ]]; then
  ARGS+=(--api-key "$VLLM_API_KEY")
fi

if [[ -n "$EXTRA_ARGS" ]]; then
  # shellcheck disable=SC2206
  EXTRA_SPLIT=( $EXTRA_ARGS )
  ARGS+=("${EXTRA_SPLIT[@]}")
fi

exec "$CONDA_BIN" run -n "$VLLM_ENV" vllm "${ARGS[@]}"
