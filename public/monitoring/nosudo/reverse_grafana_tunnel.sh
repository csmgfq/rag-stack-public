#!/usr/bin/env bash
set -euo pipefail

LOCAL_GRAFANA_PORT="${LOCAL_GRAFANA_PORT:-13000}"
REMOTE_MAC_PORT="${REMOTE_MAC_PORT:-11300}"
SSH_PORT="${SSH_PORT:-22}"
MAC_SSH_TARGETS="${MAC_SSH_TARGETS:-jiangzhiming@10.198.251.140 jiangzhiming@jiangzhimingmac.local}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reverse_grafana_tunnel.log"

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"
}

probe_existing_tunnel() {
  local target="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new -p "$SSH_PORT" "$target" \
    "bash -lc 'lsof -nP -iTCP:${REMOTE_MAC_PORT} -sTCP:LISTEN >/dev/null 2>&1 && curl -fsS -m 3 http://127.0.0.1:${REMOTE_MAC_PORT}/api/health >/dev/null 2>&1'" >/dev/null 2>&1
}

while true; do
  for target in $MAC_SSH_TARGETS; do
    if probe_existing_tunnel "$target"; then
      log "target=$target already has healthy listener :$REMOTE_MAC_PORT; skip reconnect"
      sleep 15
      continue
    fi

    log "connecting target=$target with -R ${REMOTE_MAC_PORT}:127.0.0.1:${LOCAL_GRAFANA_PORT}"
    if ssh \
      -o BatchMode=yes \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 \
      -o TCPKeepAlive=yes \
      -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=8 \
      -N -R "${REMOTE_MAC_PORT}:127.0.0.1:${LOCAL_GRAFANA_PORT}" \
      "$target" -p "$SSH_PORT"; then
      log "target=$target tunnel exited normally"
    else
      rc=$?
      log "target=$target tunnel exited rc=$rc"
    fi
    sleep 2
  done
  sleep 3
done
