#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$ROOT/run"
REMOTE_MAC_PORT="${REMOTE_MAC_PORT:-11300}"
LOCAL_GRAFANA_PORT="${LOCAL_GRAFANA_PORT:-13000}"

for name in reverse_grafana_tunnel grafana prometheus fnos_transfer_exporter lm_exporter; do
  pid_file="$RUN_DIR/${name}.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      echo "Stopped $name (pid=$pid)"
    else
      echo "$name already stopped"
    fi
    rm -f "$pid_file"
  else
    echo "No pid file for $name"
  fi
done

pkill -f "$ROOT/reverse_grafana_tunnel.sh" >/dev/null 2>&1 || true
pkill -f "ssh .* -R ${REMOTE_MAC_PORT}:127.0.0.1:${LOCAL_GRAFANA_PORT}" >/dev/null 2>&1 || true
