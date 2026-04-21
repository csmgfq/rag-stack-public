#!/usr/bin/env bash
set -euo pipefail
TSIP="${TSIP:-$(tailscale ip -4 | head -n1)}"
LOG_DIR=/root/tailscale-proxy/logs
PID_FILE=/root/tailscale-proxy/socat.pids
mkdir -p "$LOG_DIR"
: > "$PID_FILE"

start_one() {
  local listen_port="$1"
  local target_host="$2"
  local target_port="$3"
  local name="$4"
  nohup socat "TCP-LISTEN:${listen_port},bind=${TSIP},reuseaddr,fork" "TCP:${target_host}:${target_port}" >"$LOG_DIR/${name}.log" 2>&1 &
  echo "$! ${name} ${listen_port}->${target_host}:${target_port}" >> "$PID_FILE"
}

# host-local services tunneled into container loopback high ports
start_one 1234 127.0.0.1 51234 lmstudio
start_one 6333 127.0.0.1 56333 qdrant_http
start_one 6334 127.0.0.1 56334 qdrant_grpc
start_one 19090 127.0.0.1 59090 prometheus
start_one 9401 127.0.0.1 59401 lm_exporter

# host service already reachable from container bridge
start_one 13000 172.17.0.1 13000 grafana
start_one 11300 172.17.0.1 13000 grafana_compat

echo "Started socat proxies on TSIP=${TSIP}"
cat "$PID_FILE"
