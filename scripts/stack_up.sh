#!/usr/bin/env bash
set -euo pipefail

# Transit mode: keep existing host runtime/monitoring as primary,
# docker layer is only forwarding/control-plane transit.
LEGACY_START="/home/jiangzhiming/workspace/llm/rag/monitoring/nosudo/start_nosudo_monitoring.sh"

if [[ -x "$LEGACY_START" ]]; then
  bash "$LEGACY_START"
fi

echo "[stack_up] transit mode ready"
