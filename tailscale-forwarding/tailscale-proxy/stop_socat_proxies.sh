#!/usr/bin/env bash
set -euo pipefail
PID_FILE=/root/tailscale-proxy/socat.pids
if [[ -f "$PID_FILE" ]]; then
  while read -r pid rest; do
    kill "$pid" >/dev/null 2>&1 || true
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi
pkill -f 'socat TCP-LISTEN:1234,bind=' || true
pkill -f 'socat TCP-LISTEN:6333,bind=' || true
pkill -f 'socat TCP-LISTEN:6334,bind=' || true
pkill -f 'socat TCP-LISTEN:19090,bind=' || true
pkill -f 'socat TCP-LISTEN:9401,bind=' || true
pkill -f 'socat TCP-LISTEN:13000,bind=' || true
pkill -f 'socat TCP-LISTEN:11300,bind=' || true
echo 'Stopped socat proxies'
